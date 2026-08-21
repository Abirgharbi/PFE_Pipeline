pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }

    triggers {
        cron('H 3 1,15 * *')
    }

    parameters {
        string(name: 'SERIES', defaultValue: 'G4,L0,L1,L4,L5,N6,U0,U3,WB,WB0,WBA,WL3', description: 'Comma-separated series list')
        choice(name: 'MODE', choices: ['Full', 'Prepare', 'Upload'], description: 'Execution mode per series')
        choice(name: 'EXISTING_DATASOURCE_MODE', choices: ['Replace', 'Add'], description: 'Upload behavior for existing datasource files')
        choice(name: 'PLACEHOLDER_POLICY', choices: ['Fail', 'Warn', 'Off'], description: 'Policy for unresolved Alfred placeholders')
        string(name: 'KB_ID', defaultValue: '793', description: 'Target KB id')
        string(name: 'JSON_SPLIT_SIZE', defaultValue: '1000', description: 'Split size for JSON upload')
        string(name: 'PYTHON_EXE', defaultValue: '', description: 'Optional Python executable path (empty = .venv auto)')
        booleanParam(name: 'SKIP_DRIVERS', defaultValue: false, description: 'Skip driver/subrepo uploads')
        booleanParam(name: 'SKIP_SCHEMA_VALIDATION', defaultValue: false, description: 'Skip schema validation gate')
        booleanParam(name: 'CONTINUE_ON_WORKFLOW_ERROR', defaultValue: false, description: 'Continue inside run_full_workflow when one repo fails')
        booleanParam(name: 'CONTINUE_ON_SERIES_FAILURE', defaultValue: false, description: 'Continue with next series if one series fails')
    }

    environment {
        PYTHONUTF8 = '1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Python') {
            steps {
                powershell '''
                    if (-not (Test-Path -LiteralPath ".venv\\Scripts\\python.exe")) {
                        python -m venv .venv
                    }
                    .\\.venv\\Scripts\\python.exe -m pip install --upgrade pip
                    .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
                '''
            }
        }

        stage('Run Pipeline + Upload To KB') {
            steps {
                withCredentials([
                    string(credentialsId: 'st-remote-user', variable: 'ST_REMOTE_USER'),
                    string(credentialsId: 'st-chatgpt-api-key', variable: 'ST_CHATGPT_API_KEY'),
                    string(credentialsId: 'github-token', variable: 'GITHUB_TOKEN')
                ]) {
                    powershell '''
                        if ([string]::IsNullOrWhiteSpace($env:ST_REMOTE_USER)) {
                            throw "Missing Jenkins credential: st-remote-user"
                        }
                        if ([string]::IsNullOrWhiteSpace($env:ST_CHATGPT_API_KEY)) {
                            throw "Missing Jenkins credential: st-chatgpt-api-key"
                        }

                        $series = @($env:SERIES -split ',' | ForEach-Object { $_.Trim().ToUpperInvariant() } | Where-Object { $_ })
                        if ($series.Count -eq 0) {
                            throw "SERIES parameter is empty"
                        }

                        $script = "pipeline_Automation/workflow/Run_Single_Series_Full_Pipeline_And_Upload.ps1"
                        if (-not (Test-Path -LiteralPath $script)) {
                            throw "Missing script: $script"
                        }

                        $failed = @()

                        foreach ($s in $series) {
                            Write-Host "===== Running series $s (Mode=$env:MODE) =====" -ForegroundColor Cyan

                            $pythonExe = $env:PYTHON_EXE
                            if ([string]::IsNullOrWhiteSpace($pythonExe)) {
                                $pythonExe = '.\\.venv\\Scripts\\python.exe'
                            }

                            $args = @(
                                '-Series', $s,
                                '-Mode', $env:MODE,
                                '-ExistingDatasourceMode', $env:EXISTING_DATASOURCE_MODE,
                                '-RemoteUser', $env:ST_REMOTE_USER,
                                '-KbId', $env:KB_ID,
                                '-JsonSplitSize', $env:JSON_SPLIT_SIZE,
                                '-PlaceholderPolicy', $env:PLACEHOLDER_POLICY,
                                '-PythonExe', $pythonExe
                            )

                            if ($env:SKIP_DRIVERS -eq 'true') {
                                $args += '-SkipDrivers'
                            }
                            if ($env:SKIP_SCHEMA_VALIDATION -eq 'true') {
                                $args += '-SkipSchemaValidation'
                            }
                            if ($env:CONTINUE_ON_WORKFLOW_ERROR -eq 'true') {
                                $args += '-ContinueOnWorkflowError'
                            }

                            & $script @args
                            if ($LASTEXITCODE -ne 0) {
                                if ($env:CONTINUE_ON_SERIES_FAILURE -eq 'true') {
                                    Write-Host "[WARN] Series $s failed (exit=$LASTEXITCODE), continuing." -ForegroundColor Yellow
                                    $failed += $s
                                    continue
                                }
                                throw "Series $s failed with exit code $LASTEXITCODE"
                            }
                        }

                        if ($failed.Count -gt 0) {
                            throw "One or more series failed: $($failed -join ', ')"
                        }
                    '''
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts allowEmptyArchive: true, artifacts: 'datasets/07_delivery/st_ready/by_series/**,logs/**,tmp/**'
        }
    }
}
