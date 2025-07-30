# 🚀 Deployment Guide for Multimodal Document Translator

## Quick Start Options

### 1. 🏠 **Run Locally**

```bash
# Make script executable and run
chmod +x run_local.sh
./run_local.sh
```

**Or manually:**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment
export PYTHONPATH=$(pwd)

# Run application
python app.py
```

**Access:** http://localhost:7860

---

## 2. ☁️ **Deploy to Google Cloud Run**

### Prerequisites
- Google Cloud account
- `gcloud` CLI installed
- Docker installed
- Project with billing enabled

### Quick Deploy
```bash
# Replace with your project ID
./deploy.sh your-project-id us-central1
```

### Manual Deploy Steps

#### Step 1: Setup Google Cloud
```bash
# Install gcloud CLI (if not installed)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Login and set project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

#### Step 2: Build and Deploy
```bash
# Build with Cloud Build
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/multimodal-document-translator

# Deploy to Cloud Run
gcloud run deploy multimodal-document-translator \
  --image gcr.io/YOUR_PROJECT_ID/multimodal-document-translator \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --concurrency 10 \
  --max-instances 5
```

---

## 3. 🐳 **Deploy with Docker**

### Build and Run Locally
```bash
# Build image
docker build -t multimodal-translator .

# Run container
docker run -p 8080:8080 multimodal-translator
```

**Access:** http://localhost:8080

### Deploy to Any Cloud Provider

#### **AWS ECS/Fargate**
```bash
# Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

docker tag multimodal-translator:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/multimodal-translator:latest
docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/multimodal-translator:latest

# Deploy with ECS service
aws ecs create-service --cluster your-cluster --service-name multimodal-translator --task-definition your-task-def
```

#### **Azure Container Instances**
```bash
# Login to Azure
az login

# Create resource group
az group create --name multimodal-translator-rg --location eastus

# Deploy container
az container create \
  --resource-group multimodal-translator-rg \
  --name multimodal-translator \
  --image multimodal-translator:latest \
  --cpu 2 \
  --memory 4 \
  --ports 8080 \
  --dns-name-label multimodal-translator-unique
```

#### **DigitalOcean App Platform**
```bash
# Create app spec
doctl apps create --spec app-spec.yaml

# Or use the web interface at:
# https://cloud.digitalocean.com/apps
```

---

## 4. 🌐 **Deploy to Other Platforms**

### **Heroku**
```bash
# Install Heroku CLI
# Create Procfile
echo "web: python app.py" > Procfile

# Deploy
heroku create multimodal-translator
git push heroku main
```

### **Railway**
```bash
# Connect GitHub repo at railway.app
# Or use CLI:
railway login
railway link
railway up
```

### **Render**
```bash
# Connect GitHub repo at render.com
# Use these settings:
# - Build Command: pip install -r requirements.txt
# - Start Command: python app.py
```

### **Fly.io**
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Deploy
fly launch
fly deploy
```

---

## 🔧 **Configuration Options**

### Environment Variables
```bash
# Port (default: 7860 local, 8080 cloud)
export PORT=8080

# Python path
export PYTHONPATH=/app

# Logging level
export LOG_LEVEL=INFO

# Memory limits
export MAX_MEMORY_MB=2048

# Worker configuration
export MAX_WORKERS=4
```

### Resource Requirements

| Component | CPU | Memory | Storage |
|-----------|-----|--------|---------|
| **Minimum** | 1 core | 2GB | 1GB |
| **Recommended** | 2 cores | 4GB | 5GB |
| **High Load** | 4 cores | 8GB | 10GB |

---

## 📊 **Monitoring and Scaling**

### Cloud Run Monitoring
```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=multimodal-document-translator"

# Monitor metrics
gcloud monitoring metrics list --filter="resource.type=cloud_run_revision"
```

### Auto-scaling Configuration
- **Min instances:** 0 (cost-effective)
- **Max instances:** 5-10 (based on load)
- **Concurrency:** 10 requests per instance
- **Timeout:** 3600s (1 hour for large documents)

---

## 🔒 **Security Considerations**

### Authentication (Optional)
```bash
# Deploy with authentication
gcloud run deploy multimodal-document-translator \
  --image gcr.io/YOUR_PROJECT_ID/multimodal-document-translator \
  --no-allow-unauthenticated
```

### HTTPS
- Cloud Run provides HTTPS by default
- Custom domains: `gcloud run domain-mappings create`

### File Upload Security
- File size limits configured in application
- File type validation
- Temporary file cleanup

---

## 🚨 **Troubleshooting**

### Common Issues

#### **Memory Issues**
```bash
# Increase memory limit
gcloud run services update multimodal-document-translator \
  --memory 8Gi --region us-central1
```

#### **Timeout Issues**
```bash
# Increase timeout
gcloud run services update multimodal-document-translator \
  --timeout 3600 --region us-central1
```

#### **Cold Start Issues**
```bash
# Set minimum instances
gcloud run services update multimodal-document-translator \
  --min-instances 1 --region us-central1
```

### Logs and Debugging
```bash
# View real-time logs
gcloud run services logs tail multimodal-document-translator --region us-central1

# Debug locally with Docker
docker run -it --entrypoint /bin/bash multimodal-translator
```

---

## 💰 **Cost Optimization**

### Cloud Run Pricing Tips
- Use **min-instances: 0** for cost savings
- Set appropriate **memory limits**
- Monitor **request patterns**
- Use **regional deployment** for better latency

### Estimated Costs (USD/month)
- **Light usage** (100 requests/day): $5-15
- **Medium usage** (1000 requests/day): $20-50  
- **Heavy usage** (10000 requests/day): $100-300

---

## 📈 **Performance Optimization**

### For Large Documents
```python
# Environment variables
export MAX_MEMORY_MB=4096
export MAX_WORKERS=2
export ENABLE_PERFORMANCE_OPTIMIZATION=true
```

### For High Throughput
```python
# Environment variables
export MAX_WORKERS=8
export ENABLE_CACHING=true
export CACHE_SIZE_LIMIT=200
```

---

## 🎯 **Next Steps**

1. **Deploy** using your preferred method
2. **Test** with sample documents
3. **Monitor** performance and costs
4. **Scale** based on usage patterns
5. **Customize** for your specific needs

**Need help?** Check the logs or create an issue in the repository!