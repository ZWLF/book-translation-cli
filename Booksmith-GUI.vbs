Option Explicit

Dim fso
Dim shell
Dim root
Dim cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

root = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "cmd /c """ & root & "\Booksmith-GUI.cmd"""

shell.Run cmd, 0, False
