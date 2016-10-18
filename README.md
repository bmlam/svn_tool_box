# svn_tool_box
I still have to deal with subversion in many of my shell scripting projects. So this repo is a tool box when it comes to doing svn related choirs

The stuff is written in python. svnHelper.py is a module containing many helper functions for other scripts which are more use-case oriented.

diffSvnTree.py compares two trees underneath the same repository, typically a trunk and a branch (or a tag if you prefer) and generates a summary report, including an abridged version of "svn diff" on file nodes which differ

svnWatchOra.py is a fine tool which extracts scripts like CREATE TABLE, CREATE VIEW, CREATE PACKAGE etc from an Oracle database, using a schema which has SELECT_CATALOG role or similar privs and DBMS_METADATA. The script files are organized in a predefined folder structure. It can then automatically check-in the folder tree into a given Subversion URL. Another practical use case for this tool is to extract the scripts from two Oracle databases and diff them, thereby visualizing the delta of the database objects for example between a test and production database.
