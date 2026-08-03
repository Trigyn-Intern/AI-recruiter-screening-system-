// Thin shell-out helper. The actual command runs in the user's
// PowerShell window (not in the browser) - we use a blob URL to
// generate a .ps1 / .bat that opens in a new terminal. That keeps the
// dashboard sandboxed and avoids needing CORS on the auth API.

function buildPs1({ cwd, command }) {
  const safe = String(command).replace(/'/g, "''");
  const safeCwd = String(cwd).replace(/'/g, "''");
  return [
    "$ErrorActionPreference = 'Continue'",
    `Set-Location -LiteralPath '${safeCwd}'`,
    `Write-Host '> ${safe}' -ForegroundColor Cyan`,
    `Invoke-Expression '${safe}'`,
    "Write-Host ''",
    "Write-Host '[done] Press Enter to close...' -ForegroundColor DarkGray",
    "$null = Read-Host",
  ].join("\n");
}

function buildBat({ cwd, command }) {
  const safeCwd = String(cwd);
  return [
    "@echo off",
    `cd /d "${safeCwd}"`,
    `echo > ${command}`,
    "echo.",
    "pause",
  ].join("\r\n");
}

export function runCommand({ kind, cwd, command, file }) {
  if (file) {
    // [View] button - open the report / profile in a new tab.
    window.open("file:///" + String(file).replace(/\\/g, "/"), "_blank");
    return;
  }

  const usePs1 = kind === "powershell" || kind === "python" || kind === "k6";
  const body = usePs1 ? buildPs1({ cwd, command }) : buildBat({ cwd, command });
  const ext = usePs1 ? "ps1" : "bat";
  const blob = new Blob([body], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `testing-dashboard-run.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
