# Task: shard-doc

## Purpose
Split a large monolithic document into smaller, focused shards for easier navigation and agent consumption.

## Usage
`*shard-doc {document} {destination}`

## Steps
1. Read the source document
2. Identify logical section boundaries (headings, topics)
3. Create one file per major section in the destination directory
4. Name files descriptively (e.g., `01-overview.md`, `02-requirements.md`)
5. Create an index file at `{destination}/index.md` linking all shards
6. Optionally add front-matter to each shard referencing the parent document

## Output
- Multiple shard files in `{destination}/`
- `{destination}/index.md` with links to all shards
