# Code Style
 - avoid code redundancy. Check if an existing function has the same logic. If it can be used without modification, use it without asking. 
 - If the function would have to be refactored, confirm with the user
 - Whenever changing .json or .jsonL files, using atomic_file_update in utils.py
 - all exceptions and potential errors in the backend (data validation, for instance) should be handled by the error function in utils.py. an is error is critical if the entirety of an expected task could not completed (including but not limited to a single reply being generated, a user being created, a handle or query being added to user settings). In the case, pass critical = True to error(). If only part of a task could not be completed but subsequent tasks may still work (including but not limited to scraping or generating replies for a list of tweets), critical = false. If the error is catching a specific HTTP exception, pass the status code of that exception to error().
 - for frontend, always use styled components. Only use style sheets to store font and color variables. Make the app feel highly interactive, incorporating animations in the background and when loading and hovering over elements. Use styled fonts (serif or monospace as appopriate) for headers and sans serif fonts for longer text (for readbility). The design should metaphorically reflect the function of the product. For exmaple, using typing animations, type writer or quill-esque designs, or flickering to reflect that it is a ghostwriting tool. 
# Workflow
- research the codebase and come up with a plan of action
- confirm the plan with the user 
- run uv sync so the dependencies are updated 

# Bash commands
