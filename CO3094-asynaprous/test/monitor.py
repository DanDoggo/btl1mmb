import psutil
import sys
import time

if len(sys.argv) < 2:
    print("Usage: python monitor.py <PID_OF_SERVER>")
    sys.exit(1)

pid = int(sys.argv[1])
try:
    process = psutil.Process(pid)
    peak_ram = 0
    peak_threads = 0
    print(f"Monitoring PID {pid}... (Press Ctrl+C to stop)")
    print("-" * 80)
    
    while True:
        # Get Resident Set Size (RSS) in Megabytes
        ram_mb = process.memory_info().rss / (1024 * 1024)
        threads = process.num_threads()
        
        # Track peaks
        if ram_mb > peak_ram:
            peak_ram = ram_mb
        if threads > peak_threads:
            peak_threads = threads
            
        print(f"Live RAM: {ram_mb:6.2f} MB | Threads: {threads:4} | Peak RAM: {peak_ram:6.2f} MB | Peak Threads: {peak_threads:4}", end="\r")
        time.sleep(0.1)  # Dropped sleep to 0.1s for faster polling

except psutil.NoSuchProcess:
    print("\nProcess ended.")
except KeyboardInterrupt:
    print(f"\nMonitoring stopped.")
    print(f"Final Peak RAM: {peak_ram:.2f} MB")
    print(f"Final Peak Threads: {peak_threads}")
