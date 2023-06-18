Option Explicit

Const ForReading = 1

Dim objFSO, objFile
Set objFSO = CreateObject("Scripting.FileSystemObject")

Dim inputFilePath, language
inputFilePath = WScript.Arguments.Item(0)
language = WScript.Arguments.Item(1)

If LCase(language) = "typescript" Then
    ParseTypeScriptFile inputFilePath
ElseIf LCase(language) = "python" Then
    ParsePythonFile inputFilePath
Else
    WScript.Echo "Unsupported language: " & language
    WScript.Quit
End If

Sub ParseTypeScriptFile(filePath)
    Dim objFile
    Set objFile = objFSO.OpenTextFile(filePath, ForReading)

    Dim objectInfos
    Set objectInfos = CreateObject("Scripting.Dictionary")

    Dim currentObjectName, currentObjectDocstring, currentObjectParams
    currentObjectName = ""
    currentObjectDocstring = ""
    Set currentObjectParams = CreateObject("Scripting.Dictionary")

    Dim line
    Do Until objFile.AtEndOfStream
        line = Trim(objFile.ReadLine)
        
        ' Check if the line starts with a docstring comment
        If Left(line, 3) = "///" Then
            ' Store the previous object information if any
            If currentObjectName <> "" Then
                objectInfos.Add currentObjectName, Array(currentObjectDocstring, currentObjectParams.Items)
                currentObjectName = ""
                currentObjectDocstring = ""
                currentObjectParams.RemoveAll
            End If
            
            ' Extract the docstring from the comment
            Dim docstring
            docstring = Trim(left(line, 4))
            
            ' Append to the current object docstring
            currentObjectDocstring = currentObjectDocstring & vbCrLf & docstring
        ElseIf InStr(line, "class ") = 1 Or InStr(line, "interface ") = 1 Or InStr(line, "function ") = 1 Then
            ' Store the previous object information if any
            If currentObjectName <> "" Then
                objectInfos.Add currentObjectName, Array(currentObjectDocstring, currentObjectParams.Items)
            End If
            
            ' Extract the object name
            Dim nameStartIndex, nameEndIndex
            nameStartIndex = InStr(line, " ") + 1
            nameEndIndex = InStr(nameStartIndex, line, " ")
            If nameEndIndex = 0 Then
                nameEndIndex = Len(line) + 1
            End If
            debug.print line, nameStartIndex, nameEndIndex - nameStartIndex
            currentObjectName = Trim(Mid(line, nameStartIndex, nameEndIndex - nameStartIndex))
            currentObjectDocstring = ""
            currentObjectParams.RemoveAll
        ElseIf InStr(line, "function ") > 0 And currentObjectName <> "" Then
            ' Extract the function parameter
            Dim functionName
            debug.print line, nameStartIndex, nameEndIndex - nameStartIndex
            functionName = Trim(Mid(line, InStr(line, " ") + 1, InStr(line, "(") - InStr(line, " ") - 1))
            
            ' Append to the current object parameters
            currentObjectParams.Add functionName, Null
        End If
    Loop
    
    ' Store the last object information if any
    If currentObjectName <> "" Then
        objectInfos.Add currentObjectName, Array(currentObjectDocstring, currentObjectParams.Items)
    End If
    
    objFile.Close

    ' Output the object information as JSON
    OutputJSON objectInfos
End Sub

Sub ParsePythonFile(filePath)
    ' TODO: Implement the Python file parsing logic
End Sub

Sub OutputJSON(data)
    Dim json, jsonString
    Set json = CreateObject("Scripting.Dictionary")
    json.Add "objects", data
    jsonString = JSONStringify(json)
    
    Dim outputFile
    Set outputFile = objFSO.CreateTextFile("documentation.json", True)
    outputFile.Write jsonString
    outputFile.Close
    
    WScript.Echo "Documentation generated and saved as documentation.json."
End Sub

Function JSONStringify(obj)
    Dim typeName
    typeName = TypeName(obj)
    
    If typeName = "Dictionary" Then
        Dim json, key, value
        Set json = CreateObject("Scripting.Dictionary")
        
        For Each key In obj.Keys
            value = obj(key)
            json.Add key, JSONStringify(value)
        Next
        
        JSONStringify = JSONStringify(json)
    ElseIf typeName = "Array" Then
        Dim jsonArray, item
        Set jsonArray = CreateObject("Scripting.Dictionary")
        
        For Each item In obj
            jsonArray.Add jsonArray.Count, JSONStringify(item)
        Next
        
        JSONStringify = "[" & Join(jsonArray.Items, ",") & "]"
    ElseIf typeName = "String" Then
        JSONStringify = """" & EscapeString(obj) & """"
    ElseIf typeName = "Null" Then
        JSONStringify = "null"
    Else
        JSONStringify = obj
    End If
End Function

Function EscapeString(str)
    Dim escapedStr
    escapedStr = Replace(str, """", """""")
    escapedStr = Replace(escapedStr, "\", "\\")
    escapedStr = Replace(escapedStr, "/", "\/")
    escapedStr = Replace(escapedStr, Chr(8), "\b")
    escapedStr = Replace(escapedStr, Chr(9), "\t")
    escapedStr = Replace(escapedStr, Chr(10), "\n")
    escapedStr = Replace(escapedStr, Chr(12), "\f")
    escapedStr = Replace(escapedStr, Chr(13), "\r")
    
    EscapeString = escapedStr
End Function

If WScript.Arguments.Count < 2 Then
    WScript.Echo "Please provide the input file path and language (typescript/python)."
    WScript.Quit
End If

generate_documentation inputFilePath, language
