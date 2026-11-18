# Обновляет поля (содержание, номера страниц) в .docx через Microsoft Word,
# сохраняет документ, экспортирует PDF и выводит число страниц.
param([Parameter(Mandatory = $true)][string]$Path)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open($Path)
    $doc.Fields.Update() | Out-Null
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    $doc.Repaginate()
    foreach ($toc in $doc.TablesOfContents) { $toc.UpdatePageNumbers() }
    $pages = $doc.ComputeStatistics(2)   # wdStatisticPages
    $doc.Save()
    $pdf = [System.IO.Path]::ChangeExtension($Path, ".pdf")
    $doc.ExportAsFixedFormat($pdf, 17)   # wdExportFormatPDF
    $doc.Close($false)
    Write-Output "PAGES=$pages"
}
finally {
    $word.Quit()
}
