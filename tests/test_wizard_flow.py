"""
End-to-end test of the Settings wizard save logic.

Strategy:
  1. Patch sys.modules['streamlit'] with a fake that exposes session_state as a
     plain dict — no browser needed.
  2. Redirect ROOT / all config paths to a tmp_path so real files are never touched.
  3. Exercise _init_wizard_state  →  per-step saves  →  verify YAML/env output.
  4. Also covers the Unicode header bug (─ / –) and the encoding fix.
"""
from __future__ import annotations

import importlib
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml


# ── Minimal Streamlit stub ─────────────────────────────────────────────────────

class _SessionState(dict):
    """dict that also supports attribute access — mirrors st.session_state."""
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v


class _CtxMgr:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class _FakeST:
    """Fake streamlit module — all widget calls are no-ops or return safe defaults."""

    session_state = _SessionState()
    sidebar = _CtxMgr()

    # Config
    def set_page_config(self, **_): pass

    # Layout
    def title(self, *a, **k): pass
    def caption(self, *a, **k): pass
    def subheader(self, *a, **k): pass
    def markdown(self, *a, **k): pass
    def divider(self, *a, **k): pass
    def write(self, *a, **k): pass
    def metric(self, *a, **k): pass
    def code(self, *a, **k): pass
    def progress(self, *a, **k): pass

    def columns(self, spec):
        n = len(spec) if isinstance(spec, list) else spec
        return [_CtxMgr() for _ in range(n)]

    def tabs(self, labels):
        return [_CtxMgr() for _ in labels]

    def expander(self, *a, **k):
        return _CtxMgr()

    def form(self, *a, **k):
        return _CtxMgr()

    # Widgets — return session_state value if key given, else a safe default
    def _widget(self, default, **kw):
        k = kw.get("key")
        if k and k in self.session_state:
            return self.session_state[k]
        return kw.get("value", default)

    def radio(self, label, options, **kw):
        return options[0]

    def text_input(self, label, **kw):
        return self._widget("", **kw)

    def text_area(self, label, **kw):
        return self._widget("", **kw)

    def number_input(self, label, **kw):
        return self._widget(kw.get("min_value", 0), **kw)

    def slider(self, label, *args, **kw):
        return self._widget(args[0] if args else 0, **kw)

    def checkbox(self, label, **kw):
        return self._widget(False, **kw)

    def toggle(self, label, **kw):
        return self._widget(False, **kw)

    def selectbox(self, label, opts, **kw):
        idx = kw.get("index", 0)
        return opts[idx]

    def file_uploader(self, *a, **k):
        return None

    def button(self, *a, **k):
        return False

    def form_submit_button(self, *a, **k):
        return False

    # Feedback
    def success(self, *a, **k): pass
    def error(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def info(self, *a, **k): pass

    # Execution
    def rerun(self): pass

    @contextmanager
    def spinner(self, msg):
        yield

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


_FAKE_ST = _FakeST()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_app(tmp_path: Path):
    """
    Install the Streamlit stub, redirect config paths to tmp_path,
    then import (or reload) ui.streamlit_app.
    Returns the module.
    """
    # Reset session_state between test runs
    _FAKE_ST.session_state.clear()
    sys.modules["streamlit"] = _FAKE_ST  # type: ignore[assignment]

    # Seed minimal YAML files so _read_yaml doesn't return empty dicts
    _seed_configs(tmp_path)

    # Remove cached module so monkeypatching of paths takes effect
    sys.modules.pop("ui.streamlit_app", None)
    sys.modules.pop("streamlit_app", None)

    spec = importlib.util.spec_from_file_location(
        "streamlit_app",
        Path(__file__).parent.parent / "ui" / "streamlit_app.py",
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]

    # exec_module runs the module body, which sets ROOT / AGENT_CONFIG / etc.
    # from the real project tree.  We patch AFTER so our values win.
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    mod.ROOT              = tmp_path  # type: ignore[attr-defined]
    mod.AGENT_CONFIG      = tmp_path / "resources" / "config" / "agent_config.yaml"
    mod.CAREER_PATHS_FILE = tmp_path / "resources" / "config" / "career_paths.yaml"
    mod.SKILLS_FILE       = tmp_path / "resources" / "skills" / "skills_profile.yaml"
    mod.RESUME_A          = tmp_path / "resources" / "resumes" / "resume_path_a.md"
    mod.RESUME_B          = tmp_path / "resources" / "resumes" / "resume_path_b.md"
    mod.ENV_FILE          = tmp_path / ".env"

    return mod


def _seed_configs(tmp_path: Path) -> None:
    """Write minimal YAML/env so the app has something to read on first load."""
    (tmp_path / "resources" / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "resources" / "skills").mkdir(parents=True, exist_ok=True)
    (tmp_path / "resources" / "resumes").mkdir(parents=True, exist_ok=True)

    agent_cfg = {
        "system":   {"timezone": "Asia/Kolkata", "log_level": "INFO", "log_file": "logs/nexus.log", "db_path": "db/nexus.db"},
        "schedule": {"scout_start": "05:00", "apply_deadline": "09:15", "scout_interval_minutes": 30},
        "llm":      {"provider": "ollama", "base_url": "http://localhost:11434", "scorer_model": "llama3.2", "temperature": 0.3},
        "scout":    {"enabled": True, "platforms": ["naukri"], "keywords": ["Senior QE Manager"], "locations": ["Hyderabad"], "exclude_keywords": ["fresher"], "max_jobs_per_run": 100, "deduplicate": True},
        "scorer":   {"enabled": True, "path_b_threshold": 72, "path_a_threshold": 60},
        "tailor":   {"enabled": True},
        "apply":    {"enabled": True, "live_mode": False, "headless": True, "slow_mo_ms": 50, "timeout_ms": 30000, "retry_attempts": 2, "on_captcha": "skip_and_flag", "candidate_experience_years": 10},
        "reporter": {"enabled": True, "channels": ["telegram"]},
        "vault":    {"credential_backend": "keyring"},
    }
    career_cfg = {
        "paths": {
            "path_a": {"name": "Stretch", "target_titles": ["Director of QA"], "score_threshold": 60, "max_per_day": 3, "human_approval_required": True, "auto_apply": False, "resume_variant": "path_a", "queue_label": "Review"},
            "path_b": {"name": "Primary", "target_titles": ["Senior QE Manager"], "score_threshold": 72, "max_per_day": 15, "human_approval_required": False, "auto_apply": True, "resume_variant": "path_b", "queue_label": "Auto-Applied"},
        },
        "scoring_signals": {"strong_positive": ["CI/CD"], "mild_positive": ["agile"], "strong_negative": ["fresher"], "mild_negative": ["gaming"]},
    }
    skills_cfg = {
        "profile": {"name": "Test User", "title": "QE Manager", "location": "Hyderabad, India", "experience_years": 10, "email": "test@example.com"},
        "summary": "10-year QE professional.",
        "preferences": {"preferred_locations": ["Hyderabad", "Remote"], "remote_ok": True, "relocation_ok": False, "notice_period_days": 30},
        "leadership":     {"team_building": {"rating": 7, "keywords": []}, "strategy": {"rating": 7, "keywords": []}, "stakeholder_management": {"rating": 7, "keywords": []}, "cross_functional": {"rating": 7, "keywords": []}, "agile_scrum": {"rating": 7, "keywords": []}},
        "qa_engineering": {"test_automation": {"rating": 8, "keywords": []}, "api_testing": {"rating": 7, "keywords": []}, "ui_automation": {"rating": 7, "keywords": []}, "performance_testing": {"rating": 6, "keywords": []}, "shift_left": {"rating": 7, "keywords": []}},
        "cicd_devops":    {"cicd_pipeline": {"rating": 7, "keywords": []}, "github_actions": {"rating": 7, "keywords": []}, "docker": {"rating": 6, "keywords": []}, "aws": {"rating": 5, "keywords": []}},
        "tools":          {"selenium": {"rating": 7, "keywords": []}, "pytest": {"rating": 7, "keywords": []}, "jira": {"rating": 7, "keywords": []}, "postman": {"rating": 6, "keywords": []}},
        "languages":      {"python": {"rating": 8, "keywords": []}, "java": {"rating": 6, "keywords": []}, "sql": {"rating": 7, "keywords": []}},
        "soft_skills":    {"communication": {"rating": 8, "keywords": []}, "mentoring": {"rating": 8, "keywords": []}},
    }

    def _w(path, data):
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    _w(tmp_path / "resources" / "config" / "agent_config.yaml",   agent_cfg)
    _w(tmp_path / "resources" / "config" / "career_paths.yaml",   career_cfg)
    _w(tmp_path / "resources" / "skills" / "skills_profile.yaml", skills_cfg)
    (tmp_path / "resources" / "resumes" / "resume_path_a.md").write_text("# Test\n", encoding="utf-8")
    (tmp_path / "resources" / "resumes" / "resume_path_b.md").write_text("# Test\n", encoding="utf-8")
    (tmp_path / ".env").write_text("CANDIDATE_EMAIL=test@example.com\n", encoding="utf-8")


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestWizardInit:
    def test_init_seeds_profile_fields(self, tmp_path):
        app = _load_app(tmp_path)
        ss = _FAKE_ST.session_state

        app._init_wizard_state()

        assert ss["wz_name"]  == "Test User"
        assert ss["wz_title"] == "QE Manager"
        assert ss["wz_exp"]   == 10
        assert ss["wz_deadline"] == "09:15"
        assert ss["wz_pb_threshold"] == 72
        assert ss["wz_pa_threshold"] == 60

    def test_init_seeds_skill_ratings(self, tmp_path):
        app = _load_app(tmp_path)
        app._init_wizard_state()
        ss = _FAKE_ST.session_state

        assert ss["wz_s_qa_engineering_test_automation"] == 8
        assert ss["wz_s_languages_python"] == 8
        assert ss["wz_s_cicd_devops_aws"] == 5

    def test_init_is_idempotent(self, tmp_path):
        app = _load_app(tmp_path)
        app._init_wizard_state()
        _FAKE_ST.session_state["wz_name"] = "Changed"
        app._init_wizard_state()  # second call must not overwrite

        assert _FAKE_ST.session_state["wz_name"] == "Changed"


class TestStep1Profile:
    def test_save_profile_writes_skills_yaml(self, tmp_path):
        app = _load_app(tmp_path)
        app._init_wizard_state()
        ss = _FAKE_ST.session_state

        ss["wz_name"]         = "Ananda Raju"
        ss["wz_email"]        = "ananda@example.com"
        ss["wz_phone"]        = "+919999999999"
        ss["wz_title"]        = "QE Manager"
        ss["wz_location"]     = "Hyderabad, India"
        ss["wz_exp"]          = 17
        ss["wz_locs"]         = "Hyderabad, Remote"
        ss["wz_summary"]      = "17-year QE professional."
        ss["wz_remote_ok"]    = True
        ss["wz_relocation_ok"]= False
        ss["wz_notice"]       = 30
        ss["wz_timezone"]     = "Asia/Kolkata"
        ss["wz_scout_start"]  = "05:00"
        ss["wz_deadline"]     = "09:15"

        app._save_profile()

        data = yaml.safe_load((tmp_path / "resources" / "skills" / "skills_profile.yaml").read_text(encoding="utf-8"))
        assert data["profile"]["name"]             == "Ananda Raju"
        assert data["profile"]["experience_years"] == 17
        assert data["summary"]                     == "17-year QE professional."
        assert data["preferences"]["preferred_locations"] == ["Hyderabad", "Remote"]
        assert data["preferences"]["remote_ok"]    is True

    def test_save_profile_writes_agent_config(self, tmp_path):
        app = _load_app(tmp_path)
        app._init_wizard_state()
        ss = _FAKE_ST.session_state
        ss["wz_timezone"]    = "Asia/Kolkata"
        ss["wz_scout_start"] = "06:00"
        ss["wz_deadline"]    = "09:00"
        ss["wz_exp"]         = 17

        app._save_profile()

        cfg = yaml.safe_load((tmp_path / "resources" / "config" / "agent_config.yaml").read_text(encoding="utf-8"))
        assert cfg["schedule"]["scout_start"]    == "06:00"
        assert cfg["schedule"]["apply_deadline"] == "09:00"
        assert cfg["apply"]["candidate_experience_years"] == 17

    def test_save_profile_writes_env(self, tmp_path):
        app = _load_app(tmp_path)
        app._init_wizard_state()
        ss = _FAKE_ST.session_state
        ss["wz_name"]     = "Ananda Raju"
        ss["wz_email"]    = "ananda@example.com"
        ss["wz_phone"]    = "+919999999999"
        ss["wz_timezone"] = "Asia/Kolkata"
        ss["wz_deadline"] = "09:15"

        app._save_profile()

        env_text = (tmp_path / ".env").read_text(encoding="utf-8")
        assert "CANDIDATE_NAME=Ananda Raju"       in env_text
        assert "CANDIDATE_EMAIL=ananda@example.com" in env_text
        assert "CANDIDATE_PHONE=+919999999999"    in env_text

    def test_save_profile_unicode_headers_no_error(self, tmp_path):
        """Regression: cp1252 can't encode ─ and – — must use utf-8."""
        app = _load_app(tmp_path)
        app._init_wizard_state()
        # Should not raise UnicodeEncodeError
        app._save_profile()
        content = (tmp_path / "resources" / "skills" / "skills_profile.yaml").read_text(encoding="utf-8")
        assert "─" in content  # header was written correctly


class TestStep2CareerPaths:
    def test_save_career_writes_career_paths_yaml(self, tmp_path):
        app = _load_app(tmp_path)
        app._init_wizard_state()
        ss = _FAKE_ST.session_state

        ss["wz_pb_titles"]    = "Senior QE Manager\nQA Manager\nLead QE"
        ss["wz_pb_threshold"] = 72
        ss["wz_pb_max"]       = 15
        ss["wz_pa_titles"]    = "Director of QA\nHead of Quality"
        ss["wz_pa_threshold"] = 60
        ss["wz_pa_max"]       = 3
        ss["wz_keywords"]     = "Senior QE Manager\nLead QE"
        ss["wz_locations"]    = "Hyderabad\nRemote"
        ss["wz_exclude"]      = "fresher\njunior"
        ss["wz_sig_sp"]       = "CI/CD\nautomation"
        ss["wz_sig_mp"]       = "agile\nscrum"
        ss["wz_sig_sn"]       = "fresher\n0-2 years"
        ss["wz_sig_mn"]       = "gaming"

        app._save_career()

        cp = yaml.safe_load((tmp_path / "resources" / "config" / "career_paths.yaml").read_text(encoding="utf-8"))
        pb = cp["paths"]["path_b"]
        pa = cp["paths"]["path_a"]

        assert pb["score_threshold"] == 72
        assert pb["max_per_day"]     == 15
        assert "Senior QE Manager"   in pb["target_titles"]
        assert "QA Manager"          in pb["target_titles"]
        assert pa["score_threshold"] == 60
        assert "Director of QA"      in pa["target_titles"]
        assert "CI/CD"               in cp["scoring_signals"]["strong_positive"]

    def test_save_career_syncs_thresholds_to_agent_config(self, tmp_path):
        app = _load_app(tmp_path)
        app._init_wizard_state()
        ss = _FAKE_ST.session_state
        ss["wz_pb_threshold"] = 75
        ss["wz_pa_threshold"] = 65
        ss["wz_pb_titles"] = "QA Manager"
        ss["wz_pa_titles"] = "Director"
        ss["wz_pb_max"] = 10
        ss["wz_pa_max"] = 3
        ss["wz_keywords"] = "QA Manager"
        ss["wz_locations"] = "Hyderabad"
        ss["wz_exclude"]   = "fresher"
        ss["wz_sig_sp"] = ss["wz_sig_mp"] = ss["wz_sig_sn"] = ss["wz_sig_mn"] = ""

        app._save_career()

        cfg = yaml.safe_load((tmp_path / "resources" / "config" / "agent_config.yaml").read_text(encoding="utf-8"))
        assert cfg["scorer"]["path_b_threshold"] == 75
        assert cfg["scorer"]["path_a_threshold"] == 65


class TestStep3Skills:
    def test_save_skills_writes_all_ratings(self, tmp_path):
        app = _load_app(tmp_path)
        app._init_wizard_state()
        ss = _FAKE_ST.session_state

        # Override a few skill ratings
        ss["wz_s_leadership_team_building"]       = 9
        ss["wz_s_qa_engineering_test_automation"]  = 10
        ss["wz_s_languages_python"]               = 9
        ss["wz_s_cicd_devops_aws"]                = 4

        app._save_skills()

        data = yaml.safe_load((tmp_path / "resources" / "skills" / "skills_profile.yaml").read_text(encoding="utf-8"))
        assert data["leadership"]["team_building"]["rating"]          == 9
        assert data["qa_engineering"]["test_automation"]["rating"]    == 10
        assert data["languages"]["python"]["rating"]                  == 9
        assert data["cicd_devops"]["aws"]["rating"]                   == 4

    def test_save_skills_preserves_keywords(self, tmp_path):
        app = _load_app(tmp_path)
        app._init_wizard_state()
        app._save_skills()

        data = yaml.safe_load((tmp_path / "resources" / "skills" / "skills_profile.yaml").read_text(encoding="utf-8"))
        # _SKILLS catalogue defines keywords — they must survive a save round-trip
        assert "CI/CD" in data["cicd_devops"]["cicd_pipeline"]["keywords"]
        assert "Python" in data["languages"]["python"]["keywords"]


class TestStep4Resumes:
    def test_resume_files_readable(self, tmp_path):
        app = _load_app(tmp_path)
        # Both resume files seeded in _seed_configs
        assert app.RESUME_A.exists()
        assert app.RESUME_B.exists()
        assert "Test" in app.RESUME_B.read_text(encoding="utf-8")


class TestFullWizardFlow:
    def test_all_four_steps_in_sequence(self, tmp_path):
        """Simulate the complete wizard: init → step 1 → step 2 → step 3."""
        app = _load_app(tmp_path)
        app._init_wizard_state()
        ss = _FAKE_ST.session_state

        # ── Step 1 ──────────────────────────────────────────────────
        ss["wz_name"]          = "Ananda Raju Pandiri"
        ss["wz_email"]         = "ananda@qmaas.com"
        ss["wz_phone"]         = "+919876543210"
        ss["wz_title"]         = "QE Manager"
        ss["wz_location"]      = "Hyderabad, India"
        ss["wz_exp"]           = 17
        ss["wz_locs"]          = "Hyderabad, Remote"
        ss["wz_summary"]       = "17-year QE leader."
        ss["wz_remote_ok"]     = True
        ss["wz_relocation_ok"] = False
        ss["wz_notice"]        = 30
        ss["wz_timezone"]      = "Asia/Kolkata"
        ss["wz_scout_start"]   = "05:00"
        ss["wz_deadline"]      = "09:15"
        app._save_wizard_step(0)

        # ── Step 2 ──────────────────────────────────────────────────
        ss["wz_pb_titles"]    = "Senior QE Manager\nQA Manager"
        ss["wz_pb_threshold"] = 72
        ss["wz_pb_max"]       = 15
        ss["wz_pa_titles"]    = "Director of QA"
        ss["wz_pa_threshold"] = 60
        ss["wz_pa_max"]       = 3
        ss["wz_keywords"]     = "Senior QE Manager"
        ss["wz_locations"]    = "Hyderabad\nRemote"
        ss["wz_exclude"]      = "fresher"
        ss["wz_sig_sp"]       = "CI/CD\ntest automation"
        ss["wz_sig_mp"]       = "agile"
        ss["wz_sig_sn"]       = "fresher"
        ss["wz_sig_mn"]       = "gaming"
        app._save_wizard_step(1)

        # ── Step 3 ──────────────────────────────────────────────────
        ss["wz_s_leadership_team_building"]      = 9
        ss["wz_s_qa_engineering_test_automation"] = 10
        ss["wz_s_soft_skills_mentoring"]         = 9
        app._save_wizard_step(2)

        # ── Verify all files ────────────────────────────────────────
        skills = yaml.safe_load((tmp_path / "resources" / "skills" / "skills_profile.yaml").read_text(encoding="utf-8"))
        cfg    = yaml.safe_load((tmp_path / "resources" / "config" / "agent_config.yaml").read_text(encoding="utf-8"))
        cp     = yaml.safe_load((tmp_path / "resources" / "config" / "career_paths.yaml").read_text(encoding="utf-8"))
        env    = (tmp_path / ".env").read_text(encoding="utf-8")

        # Profile
        assert skills["profile"]["name"]             == "Ananda Raju Pandiri"
        assert skills["profile"]["experience_years"] == 17
        assert skills["summary"]                     == "17-year QE leader."

        # Schedule
        assert cfg["schedule"]["scout_start"]        == "05:00"
        assert cfg["schedule"]["apply_deadline"]     == "09:15"

        # Career paths
        assert cp["paths"]["path_b"]["score_threshold"] == 72
        assert "Senior QE Manager" in cp["paths"]["path_b"]["target_titles"]
        assert "CI/CD"             in cp["scoring_signals"]["strong_positive"]
        assert cfg["scorer"]["path_b_threshold"]        == 72

        # Skills
        assert skills["leadership"]["team_building"]["rating"]         == 9
        assert skills["qa_engineering"]["test_automation"]["rating"]   == 10
        assert skills["soft_skills"]["mentoring"]["rating"]            == 9

        # Env
        assert "CANDIDATE_NAME=Ananda Raju Pandiri" in env
        assert "CANDIDATE_EMAIL=ananda@qmaas.com"   in env

    def test_resume_apply_to_state_populates_career_paths(self, tmp_path):
        """LLM-extracted career fields must pre-fill all Step 2 session_state keys."""
        app = _load_app(tmp_path)
        app._init_wizard_state()

        parsed = {
            "name": "Ananda Raju",
            "career": {
                "path_b_titles":    ["Senior QE Manager", "QA Manager", "Lead QE"],
                "path_a_titles":    ["Director of QA", "Head of Quality"],
                "search_keywords":  ["Senior QE Manager", "automation", "CI/CD"],
                "strong_positives": ["automation architecture", "CI/CD", "shift-left"],
                "mild_positives":   ["agile", "Playwright"],
                "strong_negatives": ["fresher", "0-2 years", "junior"],
                "mild_negatives":   ["gaming", "hardware"],
            },
        }

        app._apply_resume_to_state(parsed)
        ss = _FAKE_ST.session_state

        assert "Senior QE Manager" in ss["wz_pb_titles"]
        assert "QA Manager"        in ss["wz_pb_titles"]
        assert "Director of QA"    in ss["wz_pa_titles"]
        assert "Senior QE Manager" in ss["wz_keywords"]
        assert "automation architecture" in ss["wz_sig_sp"]
        assert "agile"             in ss["wz_sig_mp"]
        assert "fresher"           in ss["wz_sig_sn"]
        assert "gaming"            in ss["wz_sig_mn"]

    def test_resume_apply_to_state_populates_all_steps(self, tmp_path):
        """Ria's extract flow: parsed resume dict pre-fills profile + all skills."""
        app = _load_app(tmp_path)
        app._init_wizard_state()

        parsed = {
            "name":             "Ananda Raju Pandiri",
            "email":            "ananda@qmaas.com",
            "phone":            "+919876543210",
            "title":            "QE Manager",
            "location":         "Hyderabad, India",
            "experience_years": 17,
            "summary":          "17-year QE leader.",
            "preferred_locations": ["Hyderabad", "Remote"],
            "skills": {
                "leadership":    {"team_building": 9, "strategy": 8, "stakeholder_management": 8, "cross_functional": 8, "agile_scrum": 8},
                "qa_engineering":{"test_automation": 10, "api_testing": 8, "ui_automation": 9, "performance_testing": 7, "shift_left": 8},
                "cicd_devops":   {"cicd_pipeline": 8, "github_actions": 8, "docker": 7, "aws": 6},
                "tools":         {"selenium": 8, "pytest": 9, "jira": 7, "postman": 7},
                "languages":     {"python": 9, "java": 7, "sql": 8},
                "soft_skills":   {"communication": 9, "mentoring": 9},
            },
        }

        app._apply_resume_to_state(parsed)
        ss = _FAKE_ST.session_state

        # Profile fields
        assert ss["wz_name"]    == "Ananda Raju Pandiri"
        assert ss["wz_exp"]     == 17
        assert ss["wz_summary"] == "17-year QE leader."
        assert ss["wz_locs"]    == "Hyderabad, Remote"

        # Skill ratings propagated to all 23 entries
        assert ss["wz_s_qa_engineering_test_automation"]  == 10
        assert ss["wz_s_leadership_team_building"]        == 9
        assert ss["wz_s_soft_skills_mentoring"]           == 9
        assert ss["wz_s_languages_python"]                == 9
        assert ss["wz_s_cicd_devops_aws"]                 == 6


class TestEncoding:
    def test_write_yaml_utf8_headers(self, tmp_path):
        """Regression: _write_yaml must not raise UnicodeEncodeError on Windows."""
        app = _load_app(tmp_path)
        out = tmp_path / "test_unicode.yaml"
        # These characters caused cp1252 failures
        header = "# ─── Nexus Skills Profile ────\n# Rate each skill 1–10."
        app._write_yaml(out, {"key": "value"}, header)
        content = out.read_text(encoding="utf-8")
        assert "─" in content
        assert "–" in content
        assert "key: value" in content

    def test_read_yaml_utf8(self, tmp_path):
        """_read_yaml must handle UTF-8 content written by _write_yaml."""
        app = _load_app(tmp_path)
        path = tmp_path / "utf8_test.yaml"
        path.write_text("name: Ananda – Raju\n", encoding="utf-8")
        data = app._read_yaml(path)
        assert data["name"] == "Ananda – Raju"

    def test_env_file_utf8(self, tmp_path):
        """_write_env / _read_env must round-trip cleanly."""
        app = _load_app(tmp_path)
        env = {"CANDIDATE_NAME": "Ananda Raju", "CANDIDATE_EMAIL": "a@b.com", "DATABASE_URL": "sqlite:///db/nexus.db", "LOG_LEVEL": "INFO", "LOG_FILE": "logs/nexus.log"}
        app._write_env(env)
        recovered = app._read_env()
        assert recovered["CANDIDATE_NAME"]  == "Ananda Raju"
        assert recovered["CANDIDATE_EMAIL"] == "a@b.com"