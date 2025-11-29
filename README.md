# Prometheus + Grafana Lab

This repository contains a ready-to-run monitoring stack (Prometheus, Alertmanager, Grafana),
example exporters, dashboards, and Kubernetes manifests for learning and testing.

## Contents
- docker-compose.yml — run the full stack locally with Docker Compose
- prometheus/ — Prometheus configuration, rules
- alertmanager/ — Alertmanager configuration
- grafana/ — provisioning & example dashboards
- app/python-exporter/ — simple Python app that exposes Prometheus metrics
- k8s/ — Kubernetes manifests (optional)
- scripts/ — helper scripts for load testing and automation

## Quickstart (Docker Compose)
1. Install Docker & Docker Compose.
2. From repo root:
```bash
docker-compose up -d
```
3. Visit:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)
- Alertmanager: http://localhost:9093

## License
MIT
