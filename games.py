import discord
import random
import asyncio
from typing import Dict, Tuple, Optional, List

# Game states
class GameState:
    def __init__(self, player1: discord.Member, player2: Optional[discord.Member] = None):
        self.player1 = player1
        self.player2 = player2
        self.current_player = player1
        self.winner = None
        self.board = None
        self.started = False
        self.message = None

class TicTacToe(GameState):
    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(player1, player2)
        self.board = ["⬜"] * 9
        self.started = True
        self.x_player = player1
        self.o_player = player2

    def make_move(self, player: discord.Member, position: int) -> bool:
        if player != self.current_player or position < 0 or position >= 9 or self.board[position] != "⬜":
            return False
            
        self.board[position] = "❌" if player == self.x_player else "⭕"
        
        # Check for winner
        if self.check_winner():
            self.winner = player
            return True
            
        # Check for draw
        if "⬜" not in self.board:
            return True
            
        self.current_player = self.o_player if player == self.x_player else self.x_player
        return True
    
    def check_winner(self) -> bool:
        # Check rows, columns and diagonals
        lines = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # columns
            [0, 4, 8], [2, 4, 6]  # diagonals
        ]
        
        for line in lines:
            if (self.board[line[0]] == self.board[line[1]] == self.board[line[2]] != "⬜"):
                return True
        return False
    
    def get_board_string(self) -> str:
        board_str = ""
        for i in range(0, 9, 3):
            board_str += "".join(self.board[i:i+3]) + "\n"
        return board_str

class Hangman(GameState):
    HANGMAN_STAGES = [
        """
           --------
           |      |
           |      
           |     
           |      
           |     
        =====
        """,
        """
           --------
           |      |
           |      O
           |     
           |      
           |     
        =====
        """,
        """
           --------
           |      |
           |      O
           |      |
           |      
           |     
        =====
        """,
        """
           --------
           |      |
           |      O
           |     /|
           |      
           |     
        =====
        """,
        """
           --------
           |      |
           |      O
           |     /|\
           |      
           |     
        =====
        """,
        """
           --------
           |      |
           |      O
           |     /|\
           |     / 
           |     
        =====
        """,
        """
           --------
           |      |
           |      O
           |     /|\
           |     / \
           |     
        =====
        """
    ]
    
    WORDS = ["PYTHON", "JAVASCRIPT", "PROGRAMMING", "DEVELOPER", "DISCORD", "BOT", "HANGMAN", "COMPUTER"]
    
    def __init__(self, player: discord.Member):
        super().__init__(player)
        self.word = random.choice(self.WORDS).upper()
        self.guessed_letters = set()
        self.incorrect_guesses = 0
        self.max_attempts = len(self.HANGMAN_STAGES) - 1
        self.started = True
    
    def guess(self, letter: str) -> Tuple[bool, bool]:  # (valid_guess, game_continues)
        letter = letter.upper()
        
        if len(letter) != 1 or not letter.isalpha() or letter in self.guessed_letters:
            return False, True
            
        self.guessed_letters.add(letter)
        
        if letter not in self.word:
            self.incorrect_guesses += 1
            if self.incorrect_guesses >= self.max_attempts:
                self.winner = None  # Player lost
                return True, False
            return True, True
            
        # Check if player won
        if all(char in self.guessed_letters for char in self.word):
            self.winner = self.player1
            return True, False
            
        return True, True
    
    def get_display_word(self) -> str:
        return " ".join(char if char in self.guessed_letters else "_" for char in self.word)
    
    def get_hangman_stage(self) -> str:
        return self.HANGMAN_STAGES[self.incorrect_guesses]

class GuessTheNumber(GameState):
    def __init__(self, player: discord.Member, min_num: int = 1, max_num: int = 100):
        super().__init__(player)
        self.number = random.randint(min_num, max_num)
        self.min_num = min_num
        self.max_num = max_num
        self.attempts = 0
        self.guesses = []
        self.started = True
    
    def make_guess(self, guess: int) -> Tuple[bool, str]:  # (game_over, message)
        try:
            guess = int(guess)
        except ValueError:
            return False, "Please enter a valid number."
            
        if guess < self.min_num or guess > self.max_num:
            return False, f"Please guess a number between {self.min_num} and {self.max_num}."
            
        self.attempts += 1
        self.guesses.append(guess)
        
        if guess < self.number:
            return False, "Too low! Try a higher number."
        elif guess > self.number:
            return False, "Too high! Try a lower number."
        else:
            self.winner = self.player1
            return True, f"🎉 Correct! You guessed the number in {self.attempts} attempts!"

class Battleship(GameState):
    BOARD_SIZE = 8
    SHIPS = [5, 4, 3, 3, 2]  # Ship sizes
    
    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(player1, player2)
        self.boards = {
            player1: self.create_board(),
            player2: self.create_board()
        }
        self.tracking_boards = {
            player1: [['🌊'] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)],
            player2: [['🌊'] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)]
        }
        self.ships = {
            player1: self.place_ships(self.boards[player1]),
            player2: self.place_ships(self.boards[player2])
        }
        self.started = True
    
    def create_board(self) -> List[List[str]]:
        return [['🌊'] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)]
    
    def place_ships(self, board: List[List[str]]) -> Dict[Tuple[int, int], int]:
        ships = {}
        for size in self.SHIPS:
            placed = False
            while not placed:
                orientation = random.choice(['horizontal', 'vertical'])
                if orientation == 'horizontal':
                    x = random.randint(0, self.BOARD_SIZE - 1)
                    y = random.randint(0, self.BOARD_SIZE - size)
                    if all(board[x][y + i] == '🌊' for i in range(size)):
                        for i in range(size):
                            board[x][y + i] = '🛳️'
                            ships[(x, y + i)] = size
                        placed = True
                else:  # vertical
                    x = random.randint(0, self.BOARD_SIZE - size)
                    y = random.randint(0, self.BOARD_SIZE - 1)
                    if all(board[x + i][y] == '🌊' for i in range(size)):
                        for i in range(size):
                            board[x + i][y] = '🛳️'
                            ships[(x + i, y)] = size
                        placed = True
        return ships
    
    def make_move(self, player: discord.Member, x: int, y: int) -> Tuple[bool, str, bool]:  # (valid_move, message, game_over)
        opponent = self.player2 if player == self.player1 else self.player1
        
        if player != self.current_player:
            return False, "It's not your turn!", False
            
        if x < 0 or x >= self.BOARD_SIZE or y < 0 or y >= self.BOARD_SIZE:
            return False, f"Coordinates must be between 0 and {self.BOARD_SIZE - 1}.", False
            
        if self.tracking_boards[player][x][y] != '🌊':
            return False, "You've already targeted this location!", False
            
        opponent_board = self.boards[opponent]
        
        if opponent_board[x][y] == '🛳️':  # Hit
            self.tracking_boards[player][x][y] = '💥'
            opponent_board[x][y] = '💥'
            
            # Check if ship is sunk
            ship_positions = [pos for pos, size in self.ships[opponent].items() 
                            if size == self.ships[opponent].get((x, y))]
            
            if all(opponent_board[px][py] == '💥' for px, py in ship_positions):
                # Mark all positions of the sunk ship with '💀'
                for px, py in ship_positions:
                    self.tracking_boards[player][px][py] = '💀'
                    opponent_board[px][py] = '💀'
                
                # Check if all ships are sunk
                if all(cell != '🛳️' for row in opponent_board for cell in row):
                    self.winner = player
                    return True, "💥 Direct hit! You've sunk all the enemy ships! You win! 🎉", True
                return True, f"💥 Direct hit! You've sunk a {ship_positions[0][1]}-length ship!", False
            return True, "💥 Direct hit!", False
        else:  # Miss
            self.tracking_boards[player][x][y] = '❌'
            self.current_player = opponent
            return True, "💧 Missed!", False
    
    def get_board_string(self, player: discord.Member, show_ships: bool = False) -> str:
        board = self.boards[player] if show_ships else self.tracking_boards[player]
        return '\n'.join(''.join(row) for row in board)
