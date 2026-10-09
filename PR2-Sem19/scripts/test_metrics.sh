#!/bin/bash
# Script to generate test metrics for Grafana/Prometheus
# This makes some API calls to generate metrics data

echo "Generating test metrics..."
echo ""

# Get API base URL from environment or use default
API_URL="${API_BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-}"

# Make some health check requests
echo "Making health check requests..."
for i in {1..5}; do
  curl -s "$API_URL/health" > /dev/null
  sleep 0.5
done

# Make some root endpoint requests
echo "Making root endpoint requests..."
for i in {1..3}; do
  curl -s "$API_URL/" > /dev/null
  sleep 0.5
done

# If API key is set, try to get jobs list
if [ -n "$API_KEY" ]; then
  echo "Making authenticated requests..."
  for i in {1..3}; do
    curl -s -H "Authorization: Bearer $API_KEY" "$API_URL/v1/jobs" > /dev/null
    sleep 0.5
  done
fi

echo ""
echo "Done! Check your metrics at:"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana: http://localhost:3000"
echo "  - Metrics endpoint: $API_URL/v1/metrics"
