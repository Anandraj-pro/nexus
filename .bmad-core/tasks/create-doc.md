# Task: create-doc

## Purpose
Create a new document from a BMAD template, customised for the current project context.

## Steps
1. If no template is specified, list all available templates from `.bmad-core/templates/`
2. Load the requested template
3. Elicit any missing information from the user
4. Populate the template with project-specific content
5. Present the draft to the user for review
6. Iterate until approved
7. Write the final document to the appropriate location (use `*doc-out` to confirm destination)

## Available Templates
See `.bmad-core/templates/` directory.

## Output
A completed markdown document saved to the project's `docs/` directory (or as specified).
