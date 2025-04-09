import multiprocessing

def worker(num):
    print(f"Worker {num} is working.")

def main():
    processes = []
    for i in range(4):
        p = multiprocessing.Process(target=worker, args=(i,))
        p.start()
        processes.append(p)
    
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()