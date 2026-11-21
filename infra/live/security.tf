# S0: security groups and rules.
#
# Decision point: who may reach the app (ingress scope)? Record it in decisions/.
# Traffic between hosts (ports in contracts/runtime.yaml):
#   app -> platform  MLflow (5000)
#   app, platform -> llm  chat (8080) and embeddings (8081)
#   app, platform -> rds  Postgres (5432)
# There is no SSH in this lab: use SSM Session Manager for a shell and port forwarding for UIs.

resource "aws_security_group" "app" {
  name        = "lab-app"
  description = "App host (Traefik, ride app, serving, mcp)"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP ingress to Traefik"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.ingress_cidrs
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "lab-app" }
}

resource "aws_security_group" "platform" {
  name        = "lab-platform"
  description = "Platform host (Dagster, MLflow)"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "MLflow from app host"
    from_port       = 5000
    to_port         = 5000
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  ingress {
    description = "MLflow from platform host itself"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    self        = true
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "lab-platform" }
}

resource "aws_security_group" "llm" {
  name        = "lab-llm"
  description = "LLM host (chat on 8080, embeddings on 8081)"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "LLM chat from app and platform"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id, aws_security_group.platform.id]
  }

  ingress {
    description     = "LLM embeddings from app and platform"
    from_port       = 8081
    to_port         = 8081
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id, aws_security_group.platform.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "lab-llm" }
}

resource "aws_security_group" "rds" {
  name        = "lab-rds"
  description = "RDS Postgres for Dagster and MLflow"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Postgres from app and platform"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id, aws_security_group.platform.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "lab-rds" }
}
