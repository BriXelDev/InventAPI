import redis

redis_client = redis.StrictRedis(host = 'InventAPI_cache', port=6379, db=0)

def clear_product_quantity_cache():
    try:
        for key in redis_client.scan_iter("products_quantity_*"):
            redis_client.delete(key)
    except Exception as e:
        print(f"Error clearing product quantity cache: {str(e)}")

