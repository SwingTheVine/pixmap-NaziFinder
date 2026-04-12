import multiprocessing
import time
import random
import math

# Worker function: fetches and processes tasks from the queue
def worker(queue):
    while True:
        task = queue.get()  # Get task from the queue
        if task is None:  # If None, exit the worker
            break
        
        # Simulate work by sleeping for a random amount of time
        print(f"Worker {multiprocessing.current_process().name} processing task: {task}")
        time.sleep(random.randint(1, 3))  # Simulate processing time

        # Simulate task processing
        result = math.sqrt(task)  # Example: take the square root of the task
        print(f"Worker {multiprocessing.current_process().name} completed task: {task}, result: {result}")

# Function to add tasks to the queue in real-time
def task_producer(queue):
    task_id = 0
    while True:
        task = random.randint(1, 100)  # Simulate generating a new task
        print(f"Adding task {task} to queue")
        queue.put(task)  # Add the task to the queue
        task_id += 1
        time.sleep(random.randint(1, 2))  # Simulate a random delay between task generation

        if task_id >= 10:  # Just to stop after 10 tasks for example
            break

    # Stop workers by sending None to the queue (signal to terminate)
    for _ in range(4):
        queue.put(None)

if __name__ == '__main__':
    # Create a Queue to hold tasks
    task_queue = multiprocessing.Queue()

    # Create 4 worker processes
    workers = []
    for _ in range(4):
        process = multiprocessing.Process(target=worker, args=(task_queue,))
        process.start()
        workers.append(process)

    # Create the task producer (simulating continuous task generation)
    producer = multiprocessing.Process(target=task_producer, args=(task_queue,))
    producer.start()

    # Wait for all the processes to finish
    producer.join()
    for worker in workers:
        worker.join()

    print("All tasks completed.")
