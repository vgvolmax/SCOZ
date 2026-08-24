param([ValidateSet('Full')][string]$Mode = 'Full')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$cyrillicTest = -join @(
    [char]0x0422,
    [char]0x0435,
    [char]0x0441,
    [char]0x0442
)
$cyrillicApp = -join @(
    [char]0x043F,
    [char]0x0440,
    [char]0x0438,
    [char]0x043B,
    [char]0x043E,
    [char]0x0436,
    [char]0x0435,
    [char]0x043D,
    [char]0x0438,
    [char]0x0435
)
$sandbox = Join-Path ([IO.Path]::GetTempPath()) ("SCOZ smoke $cyrillicTest with spaces " + [guid]::NewGuid())
$app = Join-Path $sandbox "SCOZ $cyrillicApp"
$env:SCOZ_NO_BROWSER = '1'

function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Invoke-Start([bool]$ExpectSuccess = $true) {
    Push-Location $app
    try { & cmd.exe /d /c start.bat; $code = $LASTEXITCODE }
    finally { Pop-Location }
    if ($ExpectSuccess -and $code -ne 0) { throw "start.bat failed: $code" }
    if (-not $ExpectSuccess -and $code -eq 0) { throw 'start.bat unexpectedly succeeded' }
    return $code
}
function Health {
    $h = Invoke-RestMethod -Uri 'http://127.0.0.1:17842/api/health' -TimeoutSec 3
    Assert-True ($h.status -eq 'ok' -and $h.app -eq 'SCOZ' -and $h.version -eq '0.1.0') 'Health identity mismatch'
}
function Stop-Scoz {
    $pidFile = Join-Path $app 'data/server.pid'
    if (Test-Path $pidFile) { $serverId = [int](Get-Content $pidFile); Stop-Process -Id $serverId -Force -ErrorAction SilentlyContinue; Start-Sleep 2 }
}
function Invoke-DbPython([string]$Code, [string[]]$Arguments = @()) {
    $python = Join-Path $app 'runtime/python.exe'
    $db = Join-Path $app 'data/scoz.db'
    $output = & $python -c $Code $db @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Database verification failed: $LASTEXITCODE" }
    return $output
}
function Assert-CoreMigration {
    $db = Join-Path $app 'data/scoz.db'
    Assert-True (Test-Path $db) 'data/scoz.db was not created'
    $code = "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(list(c.execute('SELECT version,name FROM schema_migrations ORDER BY version')))"
    $rows = Invoke-DbPython $code
    Assert-True ($rows -eq "[(1, 'core_foundation'), (2, 'ozon_products_import'), (3, 'ozon_search_visibility_import'), (4, 'pr5_query_data'), (5, 'benchmark_selection')]") 'Migration metadata mismatch'
    $schemaCode = "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); expected={'product_relevant_queries','benchmark_sets','benchmark_set_revisions','benchmark_members'}; actual={r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")}; assert expected <= actual; print('PASS')"
    Assert-True ((Invoke-DbPython $schemaCode) -contains 'PASS') 'PR6 schema missing'
}
function Assert-Pr6Assets {
    $keystore = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:17842/assets/js/keystore.js' -TimeoutSec 3
    $index = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:17842/' -TimeoutSec 3
    Assert-True ($keystore.StatusCode -eq 200 -and $keystore.Content.Contains('ScozKeystore')) 'Keystore asset unavailable'
    Assert-True ($index.Content.Contains('competitors-workspace') -and $index.Content.Contains('mpstats-token')) 'PR6 UI markers unavailable'
    try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:17842/api/products/999999/relevant-queries' -TimeoutSec 3 | Out-Null; throw 'Missing-product relevance unexpectedly succeeded' }
    catch { Assert-True ($_.Exception.Response.StatusCode.value__ -eq 404) 'PR6 relevance error mapping mismatch' }
    try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:17842/api/products/999999/benchmark' -TimeoutSec 3 | Out-Null; throw 'Missing-product benchmark unexpectedly succeeded' }
    catch { Assert-True ($_.Exception.Response.StatusCode.value__ -eq 404) 'PR6 benchmark error mapping mismatch' }
}
function Assert-Pr6Workflow {
    $seed = "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA foreign_keys=ON'); t='2026-01-01T00:00:00+00:00'; own=c.execute('INSERT INTO products(is_owned,created_at,updated_at) VALUES(1,?,?)',(t,t)).lastrowid; comp=c.execute('INSERT INTO products(is_owned,created_at,updated_at) VALUES(0,?,?)',(t,t)).lastrowid; c.execute(\"INSERT INTO product_external_identities(product_id,source,identity_type,identity_value,source_account_scope,created_at) VALUES(?,?,?,?,?,?)\",(own,'ozon','ozon_product_id','700001','',t)); c.execute(\"INSERT INTO product_external_identities(product_id,source,identity_type,identity_value,source_account_scope,created_at) VALUES(?,?,?,?,?,?)\",(comp,'ozon','ozon_product_id','700002','',t)); q=c.execute('INSERT INTO search_queries(query_text,created_at) VALUES(?,?)',('portable query',t)).lastrowid; b=c.execute(\"INSERT INTO import_batches(source,import_kind,status,started_at) VALUES('ozon','portable','SUCCESS',?)\",(t,)).lastrowid; a=c.execute(\"INSERT INTO source_artifacts(import_batch_id,artifact_kind,content_sha256,byte_size,created_at) VALUES(?,?,?,?,?)\",(b,'portable','a'*64,1,t)).lastrowid; c.execute(\"INSERT INTO product_query_snapshots(product_id,search_query_id,period_start,period_end,revision,supersedes_snapshot_id,payload_sha256,import_batch_id,source_artifact_id,imported_at,searched_users,seen_users,position_state,average_position,search_to_card_conversion_pct,search_to_order_conversion_pct,ordered_units,ordered_revenue_rub) VALUES(?,?,?,?,1,NULL,?,?,?,?,1,1,'KNOWN',1,'1','1',1,'1')\",(own,q,'2026-01-01','2026-01-31','b'*64,b,a,t)); c.commit(); print(f'{own}|{comp}|{q}')"
    $ids = (Invoke-DbPython $seed).Split('|')
    $own = $ids[0]; $comp = [int]$ids[1]; $query = [int]$ids[2]
    $headers = @{ 'Content-Type' = 'application/json' }
    $relevance = Invoke-RestMethod -Method Put -Headers $headers -Uri "http://127.0.0.1:17842/api/products/$own/relevant-queries" -Body (@{search_query_ids=@($query)} | ConvertTo-Json)
    Assert-True ($relevance.changed -and $relevance.selected_count -eq 1) 'PR6 relevance write failed'
    $revision = Invoke-RestMethod -Method Post -Headers $headers -Uri "http://127.0.0.1:17842/api/products/$own/benchmark/revisions" -Body (@{member_product_ids=@($comp)} | ConvertTo-Json)
    Assert-True ($revision.result -eq 'CREATED' -and $revision.revision.revision -eq 1) 'PR6 revision creation failed'
    $same = Invoke-RestMethod -Method Post -Headers $headers -Uri "http://127.0.0.1:17842/api/products/$own/benchmark/revisions" -Body (@{member_product_ids=@($comp)} | ConvertTo-Json)
    Assert-True ($same.result -eq 'NO_CHANGE' -and $same.revision.revision -eq 1) 'PR6 no-change semantics failed'
}
function Add-ProductSentinel {
    $code = "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); x='2000-01-01T00:00:00+00:00'; q=c.execute('INSERT INTO products (is_owned,created_at,updated_at) VALUES (0,?,?)',(x,x)); c.commit(); print(q.lastrowid)"
    return [int](Invoke-DbPython $code)
}
function Assert-ProductSentinel([int]$ProductId) {
    $code = "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print('|'.join(map(str,c.execute('SELECT is_owned,created_at,updated_at FROM products WHERE id=?',(int(sys.argv[2]),)).fetchone())))"
    $row = Invoke-DbPython $code @($ProductId.ToString())
    Assert-True ($row -eq '0|2000-01-01T00:00:00+00:00|2000-01-01T00:00:00+00:00') 'Product sentinel changed or disappeared'
}
function Add-PortableImports {
    $python = Join-Path $app 'runtime/python.exe'
    $code = "from io import BytesIO; from pathlib import Path; import sys; from tests.xlsx_factory import build_ozon_products_workbook,build_ozon_search_visibility_workbook; from backend.application.ozon_products_import import import_ozon_products_xlsx; from backend.application.ozon_search_visibility_import import import_ozon_search_visibility_xlsx; db=Path(sys.argv[1]); data=db.parent; a=import_ozon_products_xlsx(upload=BytesIO(build_ozon_products_workbook()),original_name='portable-pr3.xlsx',db_path=db,data_dir=data); b=import_ozon_search_visibility_xlsx(upload=BytesIO(build_ozon_search_visibility_workbook()),original_name='portable-pr4.xlsx',db_path=db,data_dir=data); assert a.status.value=='SUCCESS' and b.status.value=='SUCCESS'; print('PASS')"
    $result = & $python -c $code (Join-Path $app 'data/scoz.db')
    Assert-True ($result -contains 'PASS') 'Portable PR3/PR4 imports failed'
}
function Assert-PortableImports {
    $code = "from pathlib import Path; import sqlite3,sys; db=Path(sys.argv[1]); c=sqlite3.connect(db); kinds=dict(c.execute('SELECT import_kind,COUNT(*) FROM import_batches GROUP BY import_kind')); assert kinds.get('ozon_products_xlsx',0)>=1 and kinds.get('ozon_search_visibility_xlsx',0)>=1; assert c.execute('SELECT COUNT(*) FROM product_snapshots').fetchone()[0]>=1; assert c.execute('SELECT COUNT(*) FROM search_visibility_snapshots').fetchone()[0]>=1; paths=[r[0] for r in c.execute('SELECT stored_relpath FROM source_artifacts WHERE stored_relpath IS NOT NULL')]; assert len(paths)>=2 and all((db.parent/p).is_file() for p in paths); print('PASS')"
    $result = Invoke-DbPython $code
    Assert-True ($result -contains 'PASS') 'Portable imports or archives did not survive'
}

try {
    New-Item -ItemType Directory -Path $app -Force | Out-Null
    & robocopy.exe $root $app /E /XD (Join-Path $root 'runtime') (Join-Path $root 'data') (Join-Path $root '.venv') (Join-Path $root '.git') '__pycache__' '.pytest_cache' /XF '*.pyc' | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed: $LASTEXITCODE" }

    Write-Host '1. CLEAN FIRST RUN'
    Invoke-Start | Out-Null; Health; Assert-Pr6Assets
    Assert-True (Test-Path (Join-Path $app 'runtime/python.exe')) 'Runtime was not prepared'
    Assert-CoreMigration
    $productSentinelId = Add-ProductSentinel
    Add-PortableImports
    Assert-PortableImports
    Assert-Pr6Workflow

    Write-Host '2. SECOND RUN / REUSE'
    Stop-Scoz
    $pythonTime = (Get-Item (Join-Path $app 'runtime/python.exe')).LastWriteTimeUtc
    $countBefore = @(
        Select-String -Path (Join-Path $app 'data/launcher.log') -SimpleMatch 'runtime setup: installing requirements' -ErrorAction SilentlyContinue
    ).Count
    Invoke-Start | Out-Null; Health
    $countAfter = @(
        Select-String -Path (Join-Path $app 'data/launcher.log') -SimpleMatch 'runtime setup: installing requirements' -ErrorAction SilentlyContinue
    ).Count
    Assert-True ((Get-Item (Join-Path $app 'runtime/python.exe')).LastWriteTimeUtc -eq $pythonTime) 'Runtime was rebuilt instead of reused'
    Assert-True ($countAfter -eq $countBefore) 'Reuse unexpectedly installed packages'
    Assert-CoreMigration
    Assert-ProductSentinel $productSentinelId
    Assert-PortableImports

    Write-Host '3. ALREADY RUNNING'
    $originalPid = [int](Get-Content (Join-Path $app 'data/server.pid'))
    Invoke-Start | Out-Null
    Assert-True ([int](Get-Content (Join-Path $app 'data/server.pid')) -eq $originalPid) 'PID changed'
    Assert-True ($null -ne (Get-Process -Id $originalPid -ErrorAction SilentlyContinue)) 'Original server stopped'

    Write-Host '4. DEPENDENCY REPAIR'
    Stop-Scoz
    Set-Content (Join-Path $app 'data/sentinel.txt') 'preserve'
    $importsPath = Join-Path $app 'data/imports'
    New-Item -ItemType Directory -Force $importsPath | Out-Null
    Set-Content (Join-Path $importsPath 'sentinel.txt') 'preserve'
    Remove-Item (Join-Path $app 'runtime/Lib/site-packages/openpyxl') -Recurse -Force
    Invoke-Start | Out-Null; Health
    $repairRecorded = @(
        Select-String `
            -Path (Join-Path $app 'data/launcher.log') `
            -SimpleMatch 'runtime setup: dependencies need repair' `
            -ErrorAction SilentlyContinue
    ).Count -gt 0
    Assert-True $repairRecorded 'Repair was not recorded'
    Assert-True (Test-Path (Join-Path $app 'data/sentinel.txt')) 'data/ sentinel was lost during repair'
    Assert-True ((Get-Content (Join-Path $app 'data/sentinel.txt')) -eq 'preserve') 'data/ sentinel changed during repair'
    Assert-True ((Get-Content (Join-Path $importsPath 'sentinel.txt')) -eq 'preserve') 'data/imports sentinel changed during repair'
    Assert-ProductSentinel $productSentinelId
    Assert-PortableImports

    Write-Host '5 + 8. DAMAGED RUNTIME / DATA PRESERVATION'
    Stop-Scoz
    Set-Content (Join-Path $app 'runtime/python.exe') 'damaged'
    Invoke-Start | Out-Null; Health
    Assert-True (Test-Path (Join-Path $app 'data/sentinel.txt')) 'data/ sentinel was lost during rebuild'
    Assert-True ((Get-Content (Join-Path $app 'data/sentinel.txt')) -eq 'preserve') 'data/ sentinel changed during rebuild'
    Assert-True ((Get-Content (Join-Path $importsPath 'sentinel.txt')) -eq 'preserve') 'data/imports sentinel changed during rebuild'
    Assert-ProductSentinel $productSentinelId
    Assert-PortableImports

    Write-Host '6. FOREIGN PORT'
    Stop-Scoz
    $foreign = Start-Process -FilePath (Join-Path $app 'runtime/python.exe') -ArgumentList @('-m','http.server','17842','--bind','127.0.0.1') -WorkingDirectory $app -PassThru -WindowStyle Hidden
    Start-Sleep 2
    Invoke-Start $false | Out-Null
    Assert-True ($null -ne (Get-Process -Id $foreign.Id -ErrorAction SilentlyContinue)) 'Foreign listener was killed'
    Stop-Process -Id $foreign.Id -Force

    Write-Host '7. SPACES + CYRILLIC PATH'
    Invoke-Start | Out-Null; Health
    Assert-CoreMigration
    Assert-ProductSentinel $productSentinelId
    Assert-PortableImports
    Write-Host '9. PR3 PORTABLE DEPENDENCIES AND IMPORT ARCHIVE'
    $portablePython = Join-Path $app 'runtime/python.exe'
    $dependencyProbe = & $portablePython -c "import importlib.metadata as m; import httpx,openpyxl,multipart; assert m.version('httpx') == '0.28.1'; assert m.version('openpyxl') == '3.1.5'; assert m.version('python-multipart') == '0.0.32'; print('PASS')"
    Assert-True ($dependencyProbe -contains 'PASS') 'PR3 dependency metadata/import validation failed'
    Assert-True (Test-Path (Join-Path $importsPath 'sentinel.txt')) 'data/imports sentinel was lost'
    $parserProbe = & $portablePython -c "from tests.xlsx_factory import build_ozon_products_workbook; from pathlib import Path; from tempfile import TemporaryDirectory; from backend.ingestion.ozon_products_xlsx import parse_ozon_products_xlsx; import os; d=TemporaryDirectory(); p=Path(d.name)/'synthetic.xlsx'; p.write_bytes(build_ozon_products_workbook()); assert len(parse_ozon_products_xlsx(p).rows)==1; d.cleanup(); print('PASS')"
    Assert-True ($parserProbe -contains 'PASS') 'Synthetic PR3 parser smoke failed'
    $importProbe = & $portablePython -c "from io import BytesIO; from pathlib import Path; import sqlite3,sys,tempfile; from tests.xlsx_factory import build_ozon_products_workbook; from backend.persistence.database import initialize_database; from backend.application.ozon_products_import import import_ozon_products_xlsx; d=Path(tempfile.mkdtemp()); db=d/'scoz.db'; initialize_database(db); r=import_ozon_products_xlsx(upload=BytesIO(build_ozon_products_workbook()),original_name='synthetic.xlsx',db_path=db,data_dir=d); c=sqlite3.connect(db); assert r.status.value=='SUCCESS'; assert c.execute('SELECT COUNT(*) FROM products').fetchone()[0]==1; assert c.execute('SELECT COUNT(*) FROM product_snapshots').fetchone()[0]==1; rel=c.execute('SELECT stored_relpath FROM source_artifacts').fetchone()[0]; assert rel and (d/rel).is_file(); print('PASS')"
    Assert-True ($importProbe -contains 'PASS') 'Synthetic PR3 import smoke failed'
    $visibilityParserProbe = & $portablePython -c "from pathlib import Path; from tempfile import TemporaryDirectory; from tests.xlsx_factory import build_ozon_search_visibility_workbook; from backend.ingestion.ozon_search_visibility_xlsx import parse_ozon_search_visibility_xlsx; d=TemporaryDirectory(); p=Path(d.name)/'visibility.part'; p.write_bytes(build_ozon_search_visibility_workbook()); assert len(parse_ozon_search_visibility_xlsx(p).rows)==1; d.cleanup(); print('PASS')"
    Assert-True ($visibilityParserProbe -contains 'PASS') 'Synthetic PR4 parser smoke failed'
    $visibilityProbe = & $portablePython -c "from io import BytesIO; from pathlib import Path; import sqlite3,tempfile; from tests.xlsx_factory import build_ozon_search_visibility_workbook; from backend.persistence.database import initialize_database; from backend.application.ozon_search_visibility_import import import_ozon_search_visibility_xlsx; d=Path(tempfile.mkdtemp()); db=d/'scoz.db'; initialize_database(db); r=import_ozon_search_visibility_xlsx(upload=BytesIO(build_ozon_search_visibility_workbook()),original_name='visibility.xlsx',db_path=db,data_dir=d); c=sqlite3.connect(db); assert r.status.value=='SUCCESS'; assert c.execute('SELECT COUNT(*) FROM search_visibility_snapshots').fetchone()[0]==1; rel=c.execute('SELECT stored_relpath FROM source_artifacts WHERE artifact_kind=?',('ozon_search_visibility_xlsx',)).fetchone()[0]; assert rel and (d/rel).is_file(); print('PASS')"
    Assert-True ($visibilityProbe -contains 'PASS') 'Synthetic PR4 import smoke failed'
    $queryProbe = & $portablePython -c "from io import BytesIO; from pathlib import Path; import hashlib,sqlite3,tempfile; from tests.xlsx_factory import build_ozon_seller_queries_workbook,build_ozon_query_metrics_workbook; from backend.persistence.database import initialize_database; from backend.application.ozon_seller_queries_import import import_ozon_seller_queries_xlsx; from backend.application.ozon_query_metrics_import import import_ozon_query_metrics_xlsx; d=Path(tempfile.mkdtemp()); db=d/'scoz.db'; initialize_database(db); a=build_ozon_seller_queries_workbook(); b=build_ozon_query_metrics_workbook(horizontal_capitalized=True,dimension_ref='A1'); x=import_ozon_seller_queries_xlsx(upload=BytesIO(a),original_name='seller.xlsx',db_path=db,data_dir=d); y=import_ozon_query_metrics_xlsx(upload=BytesIO(b),original_name='metrics.xlsx',db_path=db,data_dir=d); c=sqlite3.connect(db); assert x.status.value=='SUCCESS' and y.status.value=='SUCCESS'; assert c.execute('SELECT COUNT(*) FROM product_query_snapshots').fetchone()[0]>=1; assert c.execute('SELECT COUNT(*) FROM query_metric_snapshots').fetchone()[0]>=1; assert c.execute('SELECT is_owned FROM products').fetchone()[0]==1; assert c.execute('SELECT COUNT(*) FROM product_snapshots').fetchone()[0]==0; rel=c.execute('SELECT stored_relpath FROM source_artifacts WHERE artifact_kind=?',('ozon_query_metrics_xlsx',)).fetchone()[0]; assert hashlib.sha256((d/rel).read_bytes()).hexdigest()==hashlib.sha256(b).hexdigest(); print('PASS')"
    Assert-True ($queryProbe -contains 'PASS') 'Synthetic PR5 query imports failed'
    $recoveryProbe = & $portablePython -c "from pathlib import Path; import sys; from backend.application.ozon_products_import import recover_interrupted_ozon_products_imports; from backend.application.ozon_search_visibility_import import recover_interrupted_ozon_search_visibility_imports; from backend.application.ozon_seller_queries_import import recover_interrupted_ozon_seller_queries_imports; from backend.application.ozon_query_metrics_import import recover_interrupted_ozon_query_metrics_imports; db=Path(sys.argv[1]); data=db.parent; recover_interrupted_ozon_products_imports(db_path=db,data_dir=data); recover_interrupted_ozon_search_visibility_imports(db_path=db,data_dir=data); recover_interrupted_ozon_seller_queries_imports(db_path=db,data_dir=data); recover_interrupted_ozon_query_metrics_imports(db_path=db,data_dir=data); print('PASS')" (Join-Path $app 'data/scoz.db')
    Assert-True ($recoveryProbe -contains 'PASS') 'Cross-kind recovery failed'
    Assert-PortableImports
    Write-Host 'PASS: all 8 PR1 Windows smoke scenarios'
}
finally {
    Stop-Scoz
    Remove-Item $sandbox -Recurse -Force -ErrorAction SilentlyContinue
}
