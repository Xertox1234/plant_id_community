import { defineRailway, github, postgres, preserve, project, redis, service, volume } from "railway/iac";

export default defineRailway(() => {
  const plant_id_community = github("Xertox1234/plant_id_community", { checkSuites: false, rootDirectory: "backend" });

  const Postgres = postgres("Postgres", { region: "us-west2" });
  Postgres.networking = { privateNetworkEndpoint: "postgres", tcpProxies: { "5432": {} } };
  const Redis = redis("Redis", { region: "us-west2" });
  Redis.deploy = { startCommand: "/bin/sh -c \"rm -rf $RAILWAY_VOLUME_MOUNT_PATH/lost+found/ && exec docker-entrypoint.sh redis-server --requirepass $REDIS_PASSWORD --save 60 1 --dir $RAILWAY_VOLUME_MOUNT_PATH\"" };
  Redis.networking = { privateNetworkEndpoint: "redis", tcpProxies: { "6379": {} } };
  const redisVolume = volume("redis-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "us-west2", sizeMB: 5000 });
  const postgresVolume = volume("postgres-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "us-west2", sizeMB: 5000 });
  const plant_id_community2 = service("plant_id_community", {
    source: plant_id_community,
    // No `build.builder`: Railway will not store DOCKERFILE through IaC (an
    // apply leaves it null and every later plan proposes it again). Null is
    // what we want: Railway then detects backend/Dockerfile, verified
    // 2026-09-23 by a deploy with no railway.json (todo 397). Railpack cannot
    // build this backend (editable -e ./packages/wagtail_forum), so never set
    // RAILPACK or NIXPACKS here, and never rename the Dockerfile.
    //
    // bin/start.sh co-locates the Celery worker with gunicorn (todo 335) and
    // materializes FIREBASE_CREDENTIALS_B64 for FCM push (todo 286). A plain
    // gunicorn start command runs neither, and nothing alarms.
    start: "bash bin/start.sh",
    preDeploy: "python manage.py migrate --noinput && python manage.py seed_default_forum && python manage.py seed_default_badges",
    healthcheck: "/api/v1/plant-identification/health/",
    healthcheckTimeout: 300,
    // restartPolicyType is omitted: ON_FAILURE is Railway's default and is
    // stored as null. The cap of 5 is what matters, since start.sh exits 1
    // when gunicorn dies and every container restart spends from it.
    deploy: { drainingSeconds: 60, restartPolicyMaxRetries: 5 },
    replicas: { "sfo": 1 },
    domains: ["api.houseplant-md.com"],
    networking: { privateNetworkEndpoint: "plantidcommunity" },
    env: { ALLOWED_HOSTS: preserve(), CELERY_BROKER_URL: preserve(), CORS_ALLOWED_ORIGINS: preserve(), CSRF_COOKIE_SAMESITE: preserve(), CSRF_TRUSTED_ORIGINS: preserve(), DATABASE_URL: preserve(), DEBUG: preserve(), DEFAULT_FROM_EMAIL: preserve(), DISABLE_COLLECTSTATIC: preserve(), EMAIL_BACKEND: preserve(), EMAIL_HOST: preserve(), EMAIL_HOST_PASSWORD: preserve(), EMAIL_HOST_USER: preserve(), EMAIL_PORT: preserve(), EMAIL_USE_TLS: preserve(), ENABLE_FILE_LOGGING: preserve(), FIREBASE_CREDENTIALS_B64: preserve(), FIREBASE_PROJECT_ID: preserve(), FRONTEND_BASE_URL: preserve(), GOOGLE_OAUTH2_CLIENT_ID: preserve(), GOOGLE_OAUTH2_CLIENT_SECRET: preserve(), JWT_SECRET_KEY: preserve(), OPENAI_API_KEY: preserve(), PLANTNET_API_KEY: preserve(), PLANT_HEALTH_API_KEY: preserve(), PLANT_ID_API_KEY: preserve(), PORT: preserve(), R2_ACCESS_KEY_ID: preserve(), R2_BUCKET_NAME: preserve(), R2_CUSTOM_DOMAIN: preserve(), R2_ENDPOINT_URL: preserve(), R2_SECRET_ACCESS_KEY: preserve(), RATELIMIT_LOG_RESOLUTION: preserve(), RATELIMIT_TRUSTED_PROXY_COUNT: preserve(), REDIS_URL: preserve(), SECRET_KEY: preserve(), SENTRY_DSN: preserve(), SENTRY_PROFILES_SAMPLE_RATE: preserve(), SENTRY_TRACES_SAMPLE_RATE: preserve(), SESSION_COOKIE_SAMESITE: preserve(), SITE_URL: preserve(), TREFLE_API_KEY: preserve(), TRUST_PROXY_SSL_HEADER: preserve(), USE_R2: preserve(), WAGTAILFORUM_SPAM_BACKEND: preserve() },
  });
  const forumPruneCron = service("forum-prune-cron", {
    source: plant_id_community,
    // Builder left null for the same reason as plant_id_community above.
    start: "python manage.py prune_forum_tombstones",
    replicas: { "us-west2": 1 },
    deploy: { cronSchedule: "0 3 * * *", restartPolicyType: "NEVER" },
    env: { ALLOWED_HOSTS: preserve(), CORS_ALLOWED_ORIGINS: preserve(), CSRF_TRUSTED_ORIGINS: preserve(), DATABASE_URL: preserve(), DEBUG: preserve(), JWT_SECRET_KEY: preserve(), PLANT_ID_API_KEY: preserve(), R2_ACCESS_KEY_ID: preserve(), R2_BUCKET_NAME: preserve(), R2_CUSTOM_DOMAIN: preserve(), R2_ENDPOINT_URL: preserve(), R2_SECRET_ACCESS_KEY: preserve(), REDIS_URL: preserve(), SECRET_KEY: preserve(), SITE_URL: preserve(), USE_R2: preserve() },
  });

  return project("PlantID Community", {
    resources: [Postgres, plant_id_community2, forumPruneCron, Redis, redisVolume, postgresVolume],
  });
});
