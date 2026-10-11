# English Lens: capture a screen rectangle in physical pixels (DPI aware) and OCR it with the
# Windows built-in engine. Prints the recognised text; exit 3 when nothing was recognised.
param([int]$X, [int]$Y, [int]$W, [int]$H, [int]$Scale = 2)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Drawing
Add-Type -Namespace W -Name U -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(System.IntPtr v);
'@
$null = [W.U]::SetProcessDpiAwarenessContext([IntPtr](-4))

$png = Join-Path $env:TEMP ('lens_' + [guid]::NewGuid().ToString('N') + '.png')
try {
    $src = New-Object System.Drawing.Bitmap($W, $H)
    $g = [System.Drawing.Graphics]::FromImage($src)
    $g.CopyFromScreen($X, $Y, 0, 0, $src.Size)
    $g.Dispose()
    if ($Scale -gt 1 -and $W * $Scale -le 10000 -and $H * $Scale -le 10000) {
        $big = New-Object System.Drawing.Bitmap([int]($W * $Scale), [int]($H * $Scale))
        $g2 = [System.Drawing.Graphics]::FromImage($big)
        $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $g2.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $g2.DrawImage($src, 0, 0, $big.Width, $big.Height)
        $g2.Dispose(); $src.Dispose(); $src = $big
    }
    $src.Save($png, [System.Drawing.Imaging.ImageFormat]::Png)
    $src.Dispose()

    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    function Await($op, $type) {
        $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
        $t.Wait(-1) | Out-Null
        $t.Result
    }
    $null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime]

    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($png)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $soft = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language('en-US')))
    if (-not $engine) { throw 'no en-US OCR engine on this machine' }
    $res = Await ($engine.RecognizeAsync($soft)) ([Windows.Media.Ocr.OcrResult])
    $text = ($res.Lines | ForEach-Object { $_.Text }) -join "`n"
    if (-not $text.Trim()) { exit 3 }
    Write-Output $text
}
finally {
    if (Test-Path $png) { Remove-Item $png -Force -ErrorAction SilentlyContinue }
}
