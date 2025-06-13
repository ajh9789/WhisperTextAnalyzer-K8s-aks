#!/bin/bash
set -e

services=(
  fastapi_service
  stt_worker
  analyzer_worker
  listener_service
)


for  svc in "${services[@]}"; do
    echo "Building: $svc"
    docker build -t ajh9789/$svc:latest ./$svc

    echo "Pushing: $svc"
    docker push ajh9789/$svc:latest

    echo  "Done: $svc"

done