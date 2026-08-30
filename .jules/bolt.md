## 2024-06-25 - Batching subprocess calls in loops

**Learning:** When executing a script, running system calls or expensive processes inside a loop for each item (N+1 queries) creates significant overhead due to constant process forks. In Bash, `pacman -Si` queries for multiple targets can be extremely slow if done one-by-one.

**Action:** Whenever verifying multiple targets via an external command, evaluate if the command accepts multiple arguments to batch process them. If it does, run it once by passing the list of targets and store the parsed output in an associative array in Bash for fast, O(1) in-memory lookups instead of executing a new subprocess inside the loop.
