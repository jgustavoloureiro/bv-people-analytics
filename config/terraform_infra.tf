# =============================================================================
# TERRAFORM — INFRA AS CODE
# People Analytics Data Platform — AWS + Azure
# =============================================================================
# NOTA: Este arquivo é FICTÍCIO para fins de portfólio.
# Em produção, os valores sensíveis (account_ids, passwords) viriam de
# AWS Secrets Manager / Azure Key Vault / HashiCorp Vault.
# =============================================================================

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  # Estado remoto (em produção)
  backend "s3" {
    bucket         = "bv-terraform-state"
    key            = "people-analytics/terraform.tfstate"
    region         = "sa-east-1"
    encrypt        = true
    dynamodb_table = "bv-terraform-locks"
  }
}

# ─── VARIÁVEIS ────────────────────────────────────────────────────────────────
variable "environment" {
  description = "Ambiente: dev | staging | prod"
  type        = string
  default     = "prod"
}
variable "region_aws"   { default = "sa-east-1" }    # São Paulo
variable "region_azure" { default = "brazilsouth" }
variable "project_name" { default = "bv-people-analytics" }

locals {
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Team        = "People Analytics & Data Engineering"
    Owner       = "josegustavoloureiro"
  }
}

# ─── AWS PROVIDER ─────────────────────────────────────────────────────────────
provider "aws" {
  region = var.region_aws
}

# ─── S3: DATA LAKE (MEDALLION ARCHITECTURE) ───────────────────────────────────
resource "aws_s3_bucket" "data_lake" {
  bucket = "${var.project_name}-${var.environment}-lake"
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle rules: Bronze → Glacier depois de 90 dias
resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  rule {
    id     = "bronze-archive"
    status = "Enabled"
    filter { prefix = "bronze/" }
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
  rule {
    id     = "gold-intelligent-tiering"
    status = "Enabled"
    filter { prefix = "gold/" }
    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }
  }
}

# Prefixos (camadas medallion)
resource "aws_s3_object" "bronze_prefix" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "bronze/"
}
resource "aws_s3_object" "silver_prefix" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "silver/"
}
resource "aws_s3_object" "gold_prefix" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "gold/"
}

# ─── IAM: ROLE DO GLUE ────────────────────────────────────────────────────────
resource "aws_iam_role" "glue_role" {
  name = "${var.project_name}-glue-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3_policy" {
  name = "glue-s3-access"
  role = aws_iam_role.glue_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucket"]
      Resource = [
        aws_s3_bucket.data_lake.arn,
        "${aws_s3_bucket.data_lake.arn}/*"
      ]
    }]
  })
}

# ─── AWS GLUE: JOBS ───────────────────────────────────────────────────────────
resource "aws_glue_job" "bronze_to_silver" {
  name         = "${var.project_name}-bronze-to-silver"
  role_arn     = aws_iam_role.glue_role.arn
  glue_version = "4.0"        # Spark 3.3
  worker_type  = "G.1X"
  number_of_workers = 3
  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.data_lake.bucket}/scripts/10_pyspark_bronze_to_silver.py"
    python_version  = "3"
  }
  default_arguments = {
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-job-insights"              = "true"
    "--job-language"                     = "python"
    "--TempDir"                          = "s3://${aws_s3_bucket.data_lake.bucket}/tmp/"
    "--BRONZE_PATH"                      = "s3://${aws_s3_bucket.data_lake.bucket}/bronze/"
    "--SILVER_PATH"                      = "s3://${aws_s3_bucket.data_lake.bucket}/silver/"
  }
  tags = local.tags
}

resource "aws_glue_job" "silver_to_gold" {
  name              = "${var.project_name}-silver-to-gold"
  role_arn          = aws_iam_role.glue_role.arn
  glue_version      = "4.0"
  worker_type       = "G.2X"    # 2x para ML
  number_of_workers = 5
  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.data_lake.bucket}/scripts/11_pyspark_silver_to_gold.py"
    python_version  = "3"
  }
  tags = local.tags
}

# ─── AWS REDSHIFT (DATA WAREHOUSE) ────────────────────────────────────────────
resource "aws_redshift_cluster" "people_analytics_dw" {
  cluster_identifier     = "${var.project_name}-dw"
  database_name          = "people_analytics"
  master_username        = "admin"
  master_password        = "REPLACE_WITH_SECRETS_MANAGER"  # Em prod: aws_secretsmanager_secret
  node_type              = "ra3.xlplus"
  cluster_type           = "multi-node"
  number_of_nodes        = 2
  encrypted              = true
  skip_final_snapshot    = false
  final_snapshot_identifier = "${var.project_name}-final-snapshot"
  iam_roles              = [aws_iam_role.glue_role.arn]
  tags                   = local.tags
}

# ─── AZURE PROVIDER ───────────────────────────────────────────────────────────
provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "people_analytics" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.region_azure
  tags     = local.tags
}

# ─── AZURE DATA LAKE STORAGE GEN2 ─────────────────────────────────────────────
resource "azurerm_storage_account" "adls" {
  name                     = "bvpeopleanalytics${var.environment}"
  resource_group_name      = azurerm_resource_group.people_analytics.name
  location                 = var.region_azure
  account_tier             = "Standard"
  account_replication_type = "ZRS"          # Zone-redundant (produção)
  account_kind             = "StorageV2"
  is_hns_enabled           = true           # Hierarchical Namespace = ADLS Gen2
  tags                     = local.tags
}

resource "azurerm_storage_data_lake_gen2_filesystem" "bronze" {
  name               = "bronze"
  storage_account_id = azurerm_storage_account.adls.id
}
resource "azurerm_storage_data_lake_gen2_filesystem" "silver" {
  name               = "silver"
  storage_account_id = azurerm_storage_account.adls.id
}
resource "azurerm_storage_data_lake_gen2_filesystem" "gold" {
  name               = "gold"
  storage_account_id = azurerm_storage_account.adls.id
}

# ─── AZURE DATABRICKS ─────────────────────────────────────────────────────────
resource "azurerm_databricks_workspace" "people_analytics" {
  name                = "${var.project_name}-databricks-${var.environment}"
  resource_group_name = azurerm_resource_group.people_analytics.name
  location            = var.region_azure
  sku                 = "premium"           # Unity Catalog disponível apenas no premium
  tags                = local.tags
}

# ─── AZURE SYNAPSE ANALYTICS ──────────────────────────────────────────────────
resource "azurerm_synapse_workspace" "people_analytics" {
  name                                 = "${var.project_name}-synapse"
  resource_group_name                  = azurerm_resource_group.people_analytics.name
  location                             = var.region_azure
  storage_data_lake_gen2_filesystem_id = azurerm_storage_data_lake_gen2_filesystem.gold.id
  sql_administrator_login              = "synapse_admin"
  sql_administrator_login_password     = "REPLACE_WITH_KEY_VAULT"
  tags                                 = local.tags
}

# ─── OUTPUTS ──────────────────────────────────────────────────────────────────
output "s3_bucket_name"     { value = aws_s3_bucket.data_lake.bucket }
output "redshift_endpoint"  { value = aws_redshift_cluster.people_analytics_dw.endpoint }
output "databricks_url"     { value = azurerm_databricks_workspace.people_analytics.workspace_url }
output "synapse_name"       { value = azurerm_synapse_workspace.people_analytics.name }
