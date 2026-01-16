# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#!
.SYNOPSIS
  Runs the Pyright "gating" commands from .github/workflows/python-validation.yml.

.DESCRIPTION
  These are the merge-blocking Pyright checks meant to catch config schema drift
  and attribute errors early.

  This script assumes you have a Python environment activated with the repo
  dependencies installed (at minimum requirements-dev.txt and any deps needed
  by reportMissingImports).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
  $fail = 0
  $failed = New-Object System.Collections.Generic.List[string]

  $gates = @(
    @{ name = 'Archive fetcher typed source config safety'; args = @(
      'adapters/copilot_archive_fetcher/copilot_archive_fetcher/models.py',
      'adapters/copilot_archive_fetcher/copilot_archive_fetcher/factory.py',
      '--level','error'
    )},
    @{ name = 'Archive store typed config safety'; args = @(
      'adapters/copilot_archive_store/copilot_archive_store/archive_store.py',
      'adapters/copilot_archive_store/copilot_archive_store/azure_blob_archive_store.py',
      'adapters/copilot_archive_store/copilot_archive_store/local_volume_archive_store.py',
      '--level','error'
    )},
    @{ name = 'Auth adapter typed config safety'; args = @(
      'adapters/copilot_auth/copilot_auth/factory.py',
      'adapters/copilot_auth/copilot_auth/github_provider.py',
      'adapters/copilot_auth/copilot_auth/google_provider.py',
      'adapters/copilot_auth/copilot_auth/microsoft_provider.py',
      '--level','error'
    )},
    @{ name = 'Chunking adapter typed config safety'; args = @(
      'adapters/copilot_chunking/copilot_chunking/chunkers.py',
      '--level','error'
    )},
    @{ name = 'Config adapter typed runtime loader safety'; args = @(
      'adapters/copilot_config/copilot_config/runtime_loader.py',
      'adapters/copilot_config/copilot_config/adapter_factory.py',
      '--level','error'
    )},
    @{ name = 'Consensus adapter typed config safety'; args = @(
      'adapters/copilot_consensus/copilot_consensus/consensus.py',
      'adapters/copilot_consensus/copilot_consensus/thread.py',
      '--level','error'
    )},
    @{ name = 'Draft diff adapter typed config safety'; args = @(
      'adapters/copilot_draft_diff/copilot_draft_diff/factory.py',
      'adapters/copilot_draft_diff/copilot_draft_diff/mock_provider.py',
      'adapters/copilot_draft_diff/copilot_draft_diff/datatracker_provider.py',
      '--level','error'
    )},
    @{ name = 'Embedding adapter typed config safety'; args = @(
      'adapters/copilot_embedding/copilot_embedding/factory.py',
      'adapters/copilot_embedding/copilot_embedding/openai_provider.py',
      'adapters/copilot_embedding/copilot_embedding/sentence_transformer_provider.py',
      '--level','error'
    )},
    @{ name = 'Error reporting adapter typed config safety'; args = @(
      'adapters/copilot_error_reporting/copilot_error_reporting/__init__.py',
      'adapters/copilot_error_reporting/copilot_error_reporting/console_error_reporter.py',
      'adapters/copilot_error_reporting/copilot_error_reporting/sentry_error_reporter.py',
      'adapters/copilot_error_reporting/copilot_error_reporting/silent_error_reporter.py',
      '--level','error'
    )},
    @{ name = 'Logging adapter typed config safety'; args = @(
      'adapters/copilot_logging/copilot_logging/factory.py',
      'adapters/copilot_logging/copilot_logging/stdout_logger.py',
      'adapters/copilot_logging/copilot_logging/silent_logger.py',
      'adapters/copilot_logging/copilot_logging/azure_monitor_logger.py',
      '--level','error'
    )},
    @{ name = 'Metrics adapter typed config safety'; args = @(
      'adapters/copilot_metrics/copilot_metrics/factory.py',
      'adapters/copilot_metrics/copilot_metrics/prometheus_metrics.py',
      'adapters/copilot_metrics/copilot_metrics/pushgateway_metrics.py',
      'adapters/copilot_metrics/copilot_metrics/azure_monitor_metrics.py',
      '--level','error'
    )},
    @{ name = 'Schema validation adapter safety'; args = @(
      'adapters/copilot_schema_validation/copilot_schema_validation/__init__.py',
      'adapters/copilot_schema_validation/copilot_schema_validation/schema_registry.py',
      'adapters/copilot_schema_validation/copilot_schema_validation/schema_provider.py',
      'adapters/copilot_schema_validation/copilot_schema_validation/file_schema_provider.py',
      'adapters/copilot_schema_validation/copilot_schema_validation/models.py',
      '--level','error'
    )},
    @{ name = 'Secrets adapter typed config safety'; args = @(
      'adapters/copilot_secrets/copilot_secrets/factory.py',
      'adapters/copilot_secrets/copilot_secrets/local_provider.py',
      'adapters/copilot_secrets/copilot_secrets/azurekeyvault_provider.py',
      '--level','error'
    )},
    @{ name = 'Startup adapter safety'; args = @(
      'adapters/copilot_startup/copilot_startup/startup_requeue.py',
      '--level','error'
    )},
    @{ name = 'Storage adapter typed config safety'; args = @(
      'adapters/copilot_storage/copilot_storage/factory.py',
      'adapters/copilot_storage/copilot_storage/mongo_document_store.py',
      'adapters/copilot_storage/copilot_storage/azure_cosmos_document_store.py',
      'adapters/copilot_storage/copilot_storage/validating_document_store.py',
      '--level','error'
    )},
    @{ name = 'Summarization adapter typed config safety'; args = @(
      'adapters/copilot_summarization/copilot_summarization/factory.py',
      'adapters/copilot_summarization/copilot_summarization/openai_summarizer.py',
      'adapters/copilot_summarization/copilot_summarization/local_llm_summarizer.py',
      'adapters/copilot_summarization/copilot_summarization/llamacpp_summarizer.py',
      '--level','error'
    )},
    @{ name = 'Vectorstore adapter typed config safety'; args = @(
      'adapters/copilot_vectorstore/copilot_vectorstore/factory.py',
      'adapters/copilot_vectorstore/copilot_vectorstore/qdrant_store.py',
      'adapters/copilot_vectorstore/copilot_vectorstore/azure_ai_search_store.py',
      'adapters/copilot_vectorstore/copilot_vectorstore/faiss_store.py',
      'adapters/copilot_vectorstore/copilot_vectorstore/inmemory.py',
      '--level','error'
    )},
    @{ name = 'Message bus adapter typed config safety'; args = @(
      'adapters/copilot_message_bus/copilot_message_bus/factory.py',
      'adapters/copilot_message_bus/copilot_message_bus/rabbitmq_publisher.py',
      'adapters/copilot_message_bus/copilot_message_bus/rabbitmq_subscriber.py',
      'adapters/copilot_message_bus/copilot_message_bus/azureservicebuspublisher.py',
      'adapters/copilot_message_bus/copilot_message_bus/azureservicebussubscriber.py',
      '--level','error'
    )},
    @{ name = 'Ingestion typed config safety'; args = @(
      'ingestion/main.py',
      'ingestion/app/service.py',
      '--level','error'
    )},
    @{ name = 'Auth typed config safety'; args = @(
      'auth/main.py',
      'auth/app/config.py',
      'auth/app/service.py',
      'auth/app/role_store.py',
      '--level','error'
    )},
    @{ name = 'Chunking typed config safety'; args = @(
      'chunking/main.py',
      'chunking/app/service.py',
      '--level','error'
    )},
    @{ name = 'Embedding typed config safety'; args = @(
      'embedding/main.py',
      'embedding/app/service.py',
      '--level','error'
    )},
    @{ name = 'Orchestrator typed config safety'; args = @(
      'orchestrator/main.py',
      'orchestrator/app/service.py',
      '--level','error'
    )},
    @{ name = 'Parsing typed config safety'; args = @(
      'parsing/main.py',
      'parsing/app/service.py',
      '--level','error'
    )},
    @{ name = 'Reporting typed config safety'; args = @(
      'reporting/main.py',
      'reporting/app/service.py',
      '--level','error'
    )},
    @{ name = 'Summarization typed config safety'; args = @(
      'summarization/main.py',
      'summarization/app/service.py',
      '--level','error'
    )}
  )

  foreach ($gate in $gates) {
    Write-Host "`n=== Pyright gate: $($gate.name) ===" -ForegroundColor Cyan
    $argsList = [string[]]$gate.args
    & pyright @argsList
    if ($LASTEXITCODE -ne 0) {
      $fail += 1
      $failed.Add($gate.name) | Out-Null
      Write-Host "Gate FAILED: $($gate.name)" -ForegroundColor Red
    } else {
      Write-Host "Gate passed: $($gate.name)" -ForegroundColor Green
    }
  }

  Write-Host "`n=== Pyright gating summary ===" -ForegroundColor Cyan
  if ($fail -gt 0) {
    Write-Host ("Failed gates ({0}):" -f $fail) -ForegroundColor Red
    foreach ($name in $failed) {
      Write-Host " - $name" -ForegroundColor Red
    }
    exit 1
  }

  Write-Host 'All pyright gating commands passed.' -ForegroundColor Green
  exit 0
}
finally {
  Pop-Location
}
