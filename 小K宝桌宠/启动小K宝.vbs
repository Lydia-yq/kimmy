Option Explicit

Dim fso, shell, projectDir, pythonw, scriptPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = projectDir & "\moon_pet.py"
pythonw = "D:\KimiData\daimon-share\daimon\runtime\python\.venv\Scripts\pythonw.exe"

If Not fso.FileExists(pythonw) Then
    pythonw = "pythonw"
End If

shell.CurrentDirectory = projectDir
On Error Resume Next
shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & scriptPath & Chr(34), 0, False

If Err.Number <> 0 Then
    MsgBox "Xiao K launch failed: " & Err.Description, vbExclamation, "Xiao K"
End If
