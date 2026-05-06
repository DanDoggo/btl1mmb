import asyncio
import time
import json

async def send_request(ip, port, path, payload):
    try:
        reader, writer = await asyncio.open_connection(ip, port)
        body_str = json.dumps(payload)
        request = f"POST {path} HTTP/1.1\r\nHost: {ip}:{port}\r\nContent-Type: application/json\r\nContent-Length: {len(body_str)}\r\nConnection: close\r\n\r\n{body_str}"
        
        writer.write(request.encode('utf-8'))
        await writer.drain()
        response = await reader.read(1024)
        writer.close()
        await writer.wait_closed()
        return b"200 OK" in response
    except Exception:
        return False

async def main():
    port = 8001
    requests_to_send = 3000 # 3,000 simultaneous users
    payload = {"sender": "Benchmark", "channel": "general", "message": "Stress test!"}

    print(f"Firing {requests_to_send} concurrent requests at Port {port}...")
    start_time = time.time()
    
    tasks = [send_request("127.0.0.1", port, "/send-peer", payload) for _ in range(requests_to_send)]
    results = await asyncio.gather(*tasks)

    total_time = time.time() - start_time
    successes = sum(1 for r in results if r)
    print(f"\nDone! {successes}/{requests_to_send} succeeded in {total_time:.2f} seconds.")

if __name__ == "__main__":
    asyncio.run(main())
