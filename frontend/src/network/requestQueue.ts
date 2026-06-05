type Task = () => Promise<any>;

let queue: Task[] = [];
let running = false;

export const requestQueue = {
  enqueue(task: Task) {
    queue.push(task);
    run();
  },
};

async function run() {
  if (running) return;

  running = true;

  while (queue.length) {
    const task = queue.shift();
    if (!task) continue;

    try {
      await task();
    } catch (err) {
      console.error("Queued request failed:", err);
    }
  }

  running = false;
}