helm upgrade --install ml-redis ./ \
  --namespace persistent-database \
  --create-namespace \
  -f values.yaml \
  --dependency-update \
  --debug     


kubectl exec -it ml-redis-master-0  -n persistent-database  -- redis-cli

127.0.0.1:6379> AUTH ml-redis-password
OK
127.0.0.1:6379> GET user:1:quota:daily:requests:used
"18"
127.0.0.1:6379> 
