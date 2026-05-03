# ScoreTris

This project implements a Tetris game in Python which grade player's move based on a heuristic function, using DFS or Beamsearch to find the next best move.

## Data Structures and Algorithms Used

- 2D array grid: stores the board state, supports collision checks, line clearing, and rendering.
- ArrayQueue: stores upcoming pieces efficiently with amortized O(1) pop from the front.
- Seven-Bag randomizer: shuffles the 7 tetromino types and pushes them into the queue for fair piece distribution.
- Heuristic evaluation: scores a board using aggregate height, holes, bumpiness, and line clear reward.
- DFS look-ahead: explores possible move sequences recursively to find the best future placement. It is useful when deeper search is needed, but it can be slower because the number of states grows quickly.
- Beam Search: keeps only the top N candidate states at each depth based on heuristic score. It is faster than full DFS and is better for real-time suggestion during gameplay.
- Priority queue / heap: used in Beam Search to maintain the best-scoring states efficiently.

## Disclamer
This project UI and Heuristic implementation is coded with AI support, tho snippets that are related to DSA (board, blocks, clearline, ...) are manually coded. 

## Run
``` bash
python3 main.py
```

## Todos
- Improve UI (add title screen, and pause menu)
- Improve FPS when calculating best move (especially at higher search depth)
- Review window to watch back and review past plays: