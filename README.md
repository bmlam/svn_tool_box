# svn_tool_box
I still have to deal with subversion in many of my shell scripting projects. So this repo is a tool box when it comes to doing svn related choirs

The stuff is written in python. svnHelper.py is a module containing many helper functions for other scripts which are more use-case oriented.

diffSvnTree.py compares two trees underneath the same repository, typically a trunk and a branch (or a tag if you prefer) and generates a summary report, including an abridged version of "svn diff" on file nodes which differ
