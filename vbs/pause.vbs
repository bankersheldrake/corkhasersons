set tArgs = WScript.Arguments
if len(tArgs(0))=0 then
    lPause = 1000
else
    lPause = tArgs(0)
end if
WScript.sleep(lPause)
wscript.quit