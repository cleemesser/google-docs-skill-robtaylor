                                                                                                        
  1. Install the skill (one command)                                                                     
                                                                                                         
  ln -s /Users/clee/code/google-docs-skill-robtaylor ~/.claude/skills/google-docs                        
                                                                                                         
  Symlink rather than copy — any edits on the python branch are picked up immediately on the next Claude 
  Code session. (Claude Code discovers skills from ~/.claude/skills/ at session start.)                  
                                                                                                         
  Verify:                                                                                                
  ls -la ~/.claude/skills/google-docs/SKILL.md                   
  Should show a valid path. That's the file Claude reads on skill invocation.                            
                                                                                                       
  2. Start a new Claude Code session                                                                     
                                                                 
  Open a new terminal — not this one. This session was started before the skill was installed, so it     
  won't see it. Run claude in a fresh shell. Any CWD is fine; Claude will cd into the user's project, and
   the skill scripts now work from any CWD (just fixed).                                                 
                                                                                                       
  3. Prompts to try

  These are ordered from "trivial sanity check" to "exercises the most novel code". Give each in a       
  separate Claude session (or one after the other in the same session) to test independently.
                                                                                                         
  a. Sanity: does Claude find the skill?                                                                 
                                                                 
  What Google Docs tools do you have access to?                                                          
  Claude should mention the google-docs skill by name and describe capabilities from SKILL.md (read,   
  create, markdown support, Drive ops, multi-account).                                                   
                                                                 
  b. Simple read (no markdown)                                                                           
                                                                                                       
  List my 5 most recent Google Drive files.
  Should invoke scripts/drive_manager.py list --max-results 5. Returns JSON which Claude summarizes.     
                                                                                                         
  c. Multi-account flag                                                                                  
                                                                                                         
  List the first 3 Drive files in my stanford account.                                                 
  Should include --account stanford in the invocation. This is the test that Claude correctly reads the  
  Multi-Account section of SKILL.md and uses it.                                                         
                                                                 
  d. Markdown creation (the high-value one)                                                              
                                                                                                         
  Create a Google Doc called "Claude Test Doc" with a heading "Summary", a paragraph
  explaining the weather today in short form, a bulleted list of 3 things I should do                    
  today, and a 2-column table with items "Item" and "Priority" for two fake tasks.                       
  Should invoke create-from-markdown with Claude-generated Markdown. This is where the whole port gets   
  exercised end-to-end: Claude's interpretation of intent → Markdown → parser → three batchUpdate calls →
   actual formatted Google Doc.                                                                          
                                                                                                         
  Ask Claude for the URL, open it, and verify:                                                         
  - Headings render as headings (not bold text)                                                          
  - Table has the right columns                                                                          
  - Bullets render as •                                                                                  
  - No stray # or | characters leaking into the body                                                     
                                                                                                         
  e. Append/edit an existing doc                                                                         
                                                                                                         
  Using the doc from (d):                                                                                
  Add a section called "Notes" at the end of that doc with the text "Testing the Python port."           
  Should invoke insert-from-markdown (or append). Verify the new section appears.                      
                                                                                                         
  f. Find-and-replace                                                                                    
                                                                                                         
  In that doc, replace "Testing" with "Verified".                                                        
  Should invoke replace. Verify in the browser.                                                          
                                                                                                         
  g. Cleanup                                                                                             
                                                                                                         
  Delete that Google Doc.                                                                              
  Should invoke drive_manager.py delete. Check that it's in your Drive trash.
                                                                                                         
  4. What to watch for                                           
                                                                                                         
  - Claude invoking the right command: Claude Code shows each Bash tool call. Eyeball them. They should  
  look like scripts/docs_manager.py create-from-markdown etc., piped JSON on stdin for mutating ops,
  --account <name> when you mentioned an account.                                                        
  - Error handling: try an invalid prompt (e.g. "read this doc: not-a-real-id"). The script returns    
  API_ERROR JSON; Claude should recognize this as an error and surface it usefully rather than claiming  
  success.                                                       
  - Token re-use: the doc-creation command shouldn't re-trigger auth — your existing                     
  token_python_default.json should refresh transparently.                                                
  - Stale cache: if Claude keeps referring to Ruby (.rb scripts) or the old auth flow, it's reading a
  cached SKILL.md. Exit Claude and restart the session.                                                  
                                                                                                       
  5. Rollback                                                                                            
                                                                                                       
  If something's catastrophically broken, remove the symlink:                                            
  rm ~/.claude/skills/google-docs                                                                      
  Claude Code falls back to having no google-docs skill until you put it back.
                                                                              
  Before you start                                                                                       
                                                                                                         
  One thing worth doing first so you have a known-good baseline: run the example scripts directly from   
  your shell (not through Claude) to confirm the skill itself works outside of Claude Code:              
                                                                                                         
  cd /Users/clee/code/google-docs-skill-robtaylor                                                      
  examples/create_from_markdown.sh    # exercises the most novel code                                    
  examples/drive_roundtrip.sh         # exercises Drive basics                                           
  examples/multi_account.sh           # confirms multi-account                                           
                                                                                                         
  If any of those fail, the skill is broken and testing through Claude will also fail — fix first. If    
  they all pass, any issue Claude surfaces is an integration/prompting issue rather than a code issue.   
                             
