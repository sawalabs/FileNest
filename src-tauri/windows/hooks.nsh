!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Stopping running FileNest processes before install/update..."
  nsExec::ExecToLog 'taskkill /F /IM filenest-backend.exe /T'
  nsExec::ExecToLog 'taskkill /F /IM filenest.exe /T'
  Sleep 500
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  DetailPrint "Stopping running FileNest processes before uninstall..."
  nsExec::ExecToLog 'taskkill /F /IM filenest-backend.exe /T'
  nsExec::ExecToLog 'taskkill /F /IM filenest.exe /T'
  Sleep 500
!macroend
