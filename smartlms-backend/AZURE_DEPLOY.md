# Azure App Service Deployment

We use Gunicorn worker class for Uvicorn (uvicorn.workers.UvicornWorker)
to match production best practices.

Use `startup.sh` as your custom startup command in Azure Portal -> Configuration.

Environment variables needed:
APP_ENV=production
DATABASE_URL=postgres://...
JWT_SECRET_KEY=...
# etc. (see .env.example)

Ensure the `export/` folder is included in your deployment artifacts.
If deploying via Git/GitHub, ensure `.gitignore` does not exclude `export/` or the model files within it.
For large model files (>100MB), you may need Git LFS or manually upload them via Kudu/SFTP.
