# Documentation Overview

Welcome to the YouTube Transcription API documentation! This guide helps you navigate and find the information you need.

## Quick Navigation

### 🚀 Getting Started

- **[Installation Guide](INSTALLATION.md)** - Complete setup instructions for local development, Docker, and production deployment
- **[Usage Examples](usage-examples.md)** - Code examples in Python, JavaScript, and cURL for common use cases

### 📚 Core Documentation

- **[API Reference](api-reference.md)** - Complete API endpoint documentation with request/response examples
- **[Configuration](CONFIGURATION.md)** - All environment variables and configuration options
- **[Architecture](architecture.md)** - System design, components, and data flow
- **[Features](features.md)** - Detailed feature descriptions and backend logic

### 🐳 Deployment & Infrastructure

- **[Docker Infrastructure](docker.md)** - Docker setup, deployment, and orchestration
- **[Infrastructure Documentation](../infrastructure/README.md)** - Kubernetes, Terraform, monitoring setup

### 🔧 Troubleshooting & Support

- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[FAQ](FAQ.md)** - Frequently asked questions

### 🧪 Testing & Development

- **[Test Documentation](../tests/README.md)** - Testing guide, test coverage, and test examples

## Documentation by Topic

### Installation & Setup

- **New to the project?** Start with [Installation Guide](INSTALLATION.md)
- **Setting up Redis?** See [Installation Guide - Redis Setup](installation.md#step-5-start-redis-required-for-job-management)
- **Docker deployment?** See [Docker Infrastructure](docker.md)
- **Configuration questions?** See [Configuration Guide](CONFIGURATION.md)

### API Usage

- **First time using the API?** See [Usage Examples](usage-examples.md)
- **Need endpoint details?** See [API Reference](api-reference.md)
- **Looking for Swagger docs?** Access at `http://localhost:8000/docs` when running locally (see [API Reference](api-reference.md#interactive-documentation))
- **Authentication help?** See [API Reference - Authentication](api-reference.md#authentication)

### Understanding the System

- **How does it work?** See [Architecture](architecture.md)
- **What features are available?** See [Features](features.md)
- **Two-path transcription strategy?** See [Architecture - Two-Path Strategy](architecture.md#two-path-transcription-strategy)
- **Processing modes?** See [Architecture - Processing Modes](architecture.md#processing-modes)

### Configuration & Customization

- **Environment variables?** See [Configuration](CONFIGURATION.md)
- **Redis configuration?** See [Configuration - Redis](configuration.md#redis-configuration)
- **Whisper model settings?** See [Configuration - Whisper Model](configuration.md#whisper-model-configuration)
- **S3 storage setup?** See [Configuration - Storage](configuration.md#storage-configuration)

### Deployment & Operations

- **Docker Compose?** See [Docker Infrastructure](docker.md)
- **Kubernetes deployment?** See [Infrastructure Documentation](../infrastructure/README.md)
- **Monitoring setup?** See [Infrastructure Documentation - Monitoring](../infrastructure/README.md)
- **Production deployment?** See [Installation Guide - Production](installation.md#production-deployment)

### Troubleshooting

- **Installation issues?** See [Troubleshooting - Installation](troubleshooting.md#installation-issues)
- **API errors?** See [Troubleshooting - API Errors](troubleshooting.md#api-errors)
- **Redis connection problems?** See [Troubleshooting - Storage Issues](troubleshooting.md#storage-issues)
- **Performance issues?** See [Troubleshooting - Performance Issues](troubleshooting.md#performance-issues)
- **General questions?** See [FAQ](FAQ.md)

### Testing & Development

- **Running tests?** See [Test Documentation](../tests/README.md)
- **Writing tests?** See [Test Documentation - Writing Tests](../tests/README.md#writing-tests)
- **Test coverage?** See [Test Documentation - Test Coverage](../tests/README.md#test-coverage)

## Documentation Files

| File                                     | Description                                     | When to Use                                               |
| ---------------------------------------- | ----------------------------------------------- | --------------------------------------------------------- |
| [installation.md](INSTALLATION.md)       | Step-by-step installation and setup             | Setting up the project for the first time                 |
| [api-reference.md](api-reference.md)     | Complete API endpoint documentation             | Integrating with the API, understanding endpoints         |
| [usage-examples.md](usage-examples.md)   | Code examples and integration guides            | Learning how to use the API with code examples            |
| [configuration.md](CONFIGURATION.md)     | Configuration options and environment variables | Configuring the application, understanding settings       |
| [architecture.md](architecture.md)       | System architecture and design decisions        | Understanding how the system works internally             |
| [features.md](features.md)               | Feature overview and backend logic              | Learning about available features and capabilities        |
| [docker.md](docker.md)                   | Docker setup and deployment                     | Deploying with Docker, understanding containers           |
| [troubleshooting.md](TROUBLESHOOTING.md) | Common issues and solutions                     | Solving problems, debugging issues                        |
| [faq.md](FAQ.md)                         | Frequently asked questions                      | Quick answers to common questions                         |
| [Test Documentation](../tests/README.md) | Testing guide and examples                      | Running tests, writing tests, understanding test coverage |

## Quick Links

### Service URLs (Local Development)

When running with Docker Compose, access these services:

- **API**: `http://localhost:8000`
  - **Swagger UI**: `http://localhost:8000/docs` - Interactive API documentation
  - **ReDoc**: `http://localhost:8000/redoc` - Alternative API documentation
- **Redis UI**: `http://localhost:8081` - Redis Commander
- **MinIO Console**: `http://localhost:9001` - S3-compatible storage UI
- **Prometheus**: `http://localhost:9090` - Metrics collection
- **Grafana**: `http://localhost:3000` - Metrics visualization

### Key Concepts

- **[Two-Path Transcription Strategy](architecture.md#two-path-transcription-strategy)** - How the system chooses between captions and ASR
- **[Processing Modes](architecture.md#processing-modes)** - Synchronous vs asynchronous processing
- **[Architecture Levels](architecture.md#architecture-levels)** - Basic, Advanced, and Production levels
- **[Job Management](api-reference.md#job-management)** - How async jobs work

## Search Tips

Looking for something specific? Try these:

- **"How do I..."** → Check [Usage Examples](usage-examples.md) or [FAQ](FAQ.md)
- **"Why is..."** → Check [Troubleshooting](TROUBLESHOOTING.md) or [FAQ](FAQ.md)
- **"What is..."** → Check [Architecture](architecture.md) or [Features](features.md)
- **"Where is..."** → Check [Configuration](CONFIGURATION.md) or [Installation Guide](INSTALLATION.md)
- **"API endpoint..."** → Check [API Reference](api-reference.md)
- **"Docker..."** → Check [Docker Infrastructure](docker.md)
- **"Redis..."** → Check [Installation Guide - Redis](installation.md#step-5-start-redis-required-for-job-management) or [Configuration - Redis](configuration.md#redis-configuration)
- **"Swagger..."** → Check [API Reference](api-reference.md) or access `http://localhost:8000/docs`
- **"Test..."** or **"Testing..."** → Check [Test Documentation](../tests/README.md)

## Contributing to Documentation

Found an error or want to improve the docs? See the main [Contributing Guidelines](../CONTRIBUTING.md).

## Additional Resources

- **Main README**: [../README.md](../README.md) - Project overview and quick start
- **Infrastructure Docs**: [../infrastructure/README.md](../infrastructure/README.md) - Kubernetes, Terraform, monitoring
- **Test Documentation**: [../tests/README.md](../tests/README.md) - Testing guide and examples
- **License**: [../LICENSE](../LICENSE) - MIT License

---

**Need help?** Check the [FAQ](FAQ.md) or [Troubleshooting Guide](TROUBLESHOOTING.md) first, or open an issue on GitHub.
