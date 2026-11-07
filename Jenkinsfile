// Pipeline de pruebas E2E de GreenITESO.
//  - Cron diario   -> SUITE=sanity (valor default del parámetro)
//  - Release prod  -> SUITE=full   (disparado desde GitHub Actions del repo de frontend vía buildWithParameters)
//
// Requisitos en Jenkins:
//  - Plugins: Pipeline, JUnit, Allure Jenkins Plugin (+ tool "allure" configurado)
//  - Sesiones de los usuarios de prueba guardadas en el agente (AUTH_MODE=refresh): una persona
//    corre UNA vez, en el agente y con el usuario de Jenkins, `uv run python -m src.utils.auth --role <rol>`
//    e inicia sesión con Microsoft. Se guardan en ~/.greeniteso-e2e/auth (fuera del workspace) y
//    cada corrida las renueva; si pasan más de 7 días sin corridas hay que repetir el login.
//  - Agente Linux/macOS con curl; las dependencias de sistema de Playwright instaladas una vez
//    (sudo npx playwright install-deps  ó  sudo uv run playwright install-deps)

pipeline {
    agent any

    parameters {
        choice(name: 'SUITE', choices: ['sanity', 'full'], description: 'Marker de pytest a correr')
        string(name: 'BASE_URL', defaultValue: 'https://greeniteso-production-frontend-682248660949.northamerica-south1.run.app', description: 'URL del frontend a probar')
        string(name: 'API_BASE_URL', defaultValue: '', description: 'URL del backend; vacío = mismo origen que BASE_URL')
        choice(name: 'AUTH_MODE', choices: ['refresh', 'mock'], description: 'refresh = ambiente desplegado; mock = stack local')
        choice(name: 'BROWSER', choices: ['chromium', 'firefox', 'webkit'], description: 'Navegador de Playwright')
        string(name: 'WORKERS', defaultValue: '4', description: 'Módulos en paralelo (pytest-xdist). "auto" = núm. de CPUs, "0" = secuencial')
        string(name: 'EXTRA_PYTEST_ARGS', defaultValue: '', description: 'Args extra, p. ej. "-k Metricas" o "tests/equipo1"')
    }

    triggers {
        // Sanity diario a las ~6 AM hora de CDMX. Los builds por cron usan los valores default (SUITE=sanity).
        cron('''TZ=America/Mexico_City
H 6 * * *''')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 90, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }

    environment {
        PATH = "${env.HOME}/.local/bin:${env.PATH}"
        HEADLESS = 'true'
        BASE_URL = "${params.BASE_URL}"
        API_BASE_URL = "${params.API_BASE_URL}"
        AUTH_MODE = "${params.AUTH_MODE}"
    }

    stages {
        stage('Setup') {
            steps {
                sh '''
                    command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
                    uv --version
                    uv sync --frozen
                    uv run playwright install "${BROWSER}"
                    rm -rf reporting/allure-results/* reporting/screenshots/* reporting/logs/*
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    uv run pytest -m "${SUITE}" \
                        --browser "${BROWSER}" \
                        -n "${WORKERS}" \
                        --reruns 1 \
                        --junitxml=reporting/junit.xml \
                        ${EXTRA_PYTEST_ARGS}
                '''
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reporting/junit.xml'
            allure includeProperties: false, results: [[path: 'reporting/allure-results']]
            archiveArtifacts allowEmptyArchive: true, artifacts: 'reporting/screenshots/**, reporting/logs/**'
        }
    }
}
