"""
AlphaLens CDK Infrastructure Stack — Week 4
=============================================
Provisions:

  DynamoDB Tables:
    AlphaLens-StockScores      — AlphaScore, RSI, MACD, anomaly flags per ticker per day
    AlphaLens-StockSummaries   — FinBERT social scores, sentiment breakdown
    AlphaLens-Predictions      — XGBoost UP/DOWN/NEUTRAL predictions

  S3 Bucket:
    alphalens-data-<account>   — Raw CSVs, processed history, model artifacts

  Lambda Functions:
    alphalens-scores-api       — GET /scores, GET /scores/{ticker}
    alphalens-history-api      — GET /history/{ticker}
    alphalens-predictions-api  — GET /predictions/{ticker}
    alphalens-nightly-pipeline — (Week 5) runs all ML scripts on a schedule

  HTTP API Gateway:
    All Lambda functions exposed via API Gateway HTTP API
    CORS enabled for frontend (localhost:3000 in dev, CloudFront URL in prod)

Deploy:
  cd alphalens/infrastructure
  source .venv/bin/activate
  pip install -r requirements.txt
  cdk deploy
"""

import os
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
)
from constructs import Construct


class InfrastructureStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── DynamoDB Tables ──────────────────────────────────────────
        # StockScores and StockSummaries already exist from Week 1 — import by name.
        # Only Predictions is new and needs to be created.

        scores_table = dynamodb.Table.from_table_name(
            self, "StockScoresTable", "StockScores"
        )

        summaries_table = dynamodb.Table.from_table_name(
            self, "StockSummariesTable", "StockSummaries"
        )

        # Helper ARN for granting write access to imported tables
        # (from_table_name returns ITable which supports grant_* methods)

        predictions_table = dynamodb.Table(
            self, "PredictionsTable",
            table_name="StockPredictions",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK",      type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # ── S3 Buckets ───────────────────────────────────────────────
        # All 3 buckets already exist from Week 1 — import by name.

        data_bucket = s3.Bucket.from_bucket_name(
            self, "RawDataBucket", "alphalens-raw-data"
        )

        model_bucket = s3.Bucket.from_bucket_name(
            self, "ModelArtifactsBucket", "alphalens-model-artifacts"
        )

        # ── Shared Lambda environment vars ───────────────────────────

        lambda_env = {
            "SCORES_TABLE":      "StockScores",
            "SUMMARIES_TABLE":   "StockSummaries",
            "PREDICTIONS_TABLE": predictions_table.table_name,
            "DATA_BUCKET":       "alphalens-raw-data",
            "MODEL_BUCKET":      "alphalens-model-artifacts",
        }

        # ── Lambda Functions ─────────────────────────────────────────

        # Scores: GET /scores, GET /scores/{ticker}
        scores_fn = _lambda.Function(
            self, "ScoresApiFunction",
            function_name="alphalens-scores-api",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="scores_handler.handler",
            code=_lambda.Code.from_asset("../backend/api_handlers"),
            environment=lambda_env,
            timeout=Duration.seconds(10),
            memory_size=256,
            description="AlphaLens — scores API (AlphaScore, SocialScore, DiscoveryScore)",
        )

        # History: GET /history/{ticker}
        history_fn = _lambda.Function(
            self, "HistoryApiFunction",
            function_name="alphalens-history-api",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="history_handler.handler",
            code=_lambda.Code.from_asset("../backend/api_handlers"),
            environment=lambda_env,
            timeout=Duration.seconds(15),
            memory_size=256,
            description="AlphaLens — OHLCV history API (from S3 CSV)",
        )

        # Predictions: GET /predictions/{ticker}
        predictions_fn = _lambda.Function(
            self, "PredictionsApiFunction",
            function_name="alphalens-predictions-api",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="predictions_handler.handler",
            code=_lambda.Code.from_asset("../backend/api_handlers"),
            environment=lambda_env,
            timeout=Duration.seconds(10),
            memory_size=256,
            description="AlphaLens — XGBoost predictions API",
        )

        # ── IAM permissions ──────────────────────────────────────────

        # Scores Lambda: read from scores + summaries tables
        scores_table.grant_read_data(scores_fn)
        summaries_table.grant_read_data(scores_fn)

        # History Lambda: read from S3 + scores table
        data_bucket.grant_read(history_fn)
        scores_table.grant_read_data(history_fn)

        # Predictions Lambda: read from predictions + scores tables
        predictions_table.grant_read_data(predictions_fn)
        scores_table.grant_read_data(predictions_fn)

        # ── HTTP API Gateway ─────────────────────────────────────────

        api = apigw.HttpApi(
            self, "AlphaLensHttpApi",
            api_name="alphalens-api",
            description="AlphaLens REST API — Week 4",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.OPTIONS],
                allow_headers=["Content-Type", "Authorization"],
                max_age=Duration.hours(1),
            ),
        )

        # Route: GET /scores
        api.add_routes(
            path="/scores",
            methods=[apigw.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "ScoresIntegration", scores_fn
            ),
        )

        # Route: GET /scores/{ticker}
        api.add_routes(
            path="/scores/{ticker}",
            methods=[apigw.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "ScoresByTickerIntegration", scores_fn
            ),
        )

        # Route: GET /history/{ticker}
        api.add_routes(
            path="/history/{ticker}",
            methods=[apigw.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "HistoryIntegration", history_fn
            ),
        )

        # Route: GET /predictions/{ticker}
        api.add_routes(
            path="/predictions/{ticker}",
            methods=[apigw.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "PredictionsIntegration", predictions_fn
            ),
        )

        # ── Nightly Pipeline Lambda ──────────────────────────────────
        # Runs after market close (6pm ET = 23:00 UTC) Mon–Fri.
        # Fetches prices → features → AlphaScore → sentiment → anomaly → XGBoost
        # → writes all results to DynamoDB + archives history CSV to S3.
        #
        # Uses a container image (ECR) because ML packages exceed Lambda's 250MB limit.

        import aws_cdk.aws_ecr as ecr

        pipeline_repo = ecr.Repository.from_repository_name(
            self, "PipelineRepo", "alphalens-nightly-pipeline"
        )

        pipeline_fn = _lambda.DockerImageFunction(
            self, "NightlyPipelineFunction",
            function_name="alphalens-nightly-pipeline",
            code=_lambda.DockerImageCode.from_ecr(
                pipeline_repo,
                tag_or_digest="latest",
            ),
            environment={
                **lambda_env,
                "FINNHUB_API_KEY": os.environ.get("FINNHUB_API_KEY", ""),
            },
            timeout=Duration.minutes(10),   # 10 min — yfinance + 10 tickers
            memory_size=1024,               # ML models need memory
            description="AlphaLens — nightly ML pipeline (runs after market close)",
        )

        # IAM: pipeline needs read/write on all 3 tables + both S3 buckets
        scores_table.grant_read_write_data(pipeline_fn)
        summaries_table.grant_read_write_data(pipeline_fn)
        predictions_table.grant_read_write_data(pipeline_fn)
        data_bucket.grant_read_write(pipeline_fn)
        model_bucket.grant_read(pipeline_fn)

        # EventBridge: trigger Mon–Fri at 23:00 UTC (6pm ET / 7pm EDT)
        rule = events.Rule(
            self, "NightlyPipelineSchedule",
            rule_name="alphalens-nightly-pipeline",
            description="Trigger AlphaLens nightly ML pipeline after market close",
            schedule=events.Schedule.cron(
                minute="0",
                hour="23",
                week_day="MON-FRI",
                month="*",
                year="*",
            ),
        )
        rule.add_target(targets.LambdaFunction(pipeline_fn))

        # ── CDK Outputs (shown after cdk deploy) ────────────────────

        CfnOutput(self, "ApiUrl",
            value=api.url or "",
            description="API Gateway base URL — paste into .env.local as NEXT_PUBLIC_API_URL",
        )
        CfnOutput(self, "DataBucketName",
            value=data_bucket.bucket_name,
            description="S3 bucket for raw data and model artifacts",
        )
        CfnOutput(self, "ScoresTableName",
            value=scores_table.table_name,
            description="DynamoDB table for stock scores",
        )
        CfnOutput(self, "PredictionsTableName",
            value=predictions_table.table_name,
            description="DynamoDB table for XGBoost predictions",
        )
