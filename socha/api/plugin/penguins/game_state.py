import _pickle as pickle
import logging
from dataclasses import dataclass
from typing import List, Optional

from socha.api.plugin.penguins.board import Board
from socha.api.plugin.penguins.coordinate import CartesianCoordinate
from socha.api.plugin.penguins.team import TeamEnum, Team, Move


class GameState:
    """
       A `GameState` contains all information, that describes the game state at a given time, that is, between two game
       moves.

       This includes:
            - the board
            - a consecutive turn number (round & turn) and who's turn it is
            - the team that has started the game
            - the number of fishes each player has
            - the last move made

       The `GameState` is thus the central object through which all essential information of the current game can be
       accessed.

       Therefore, for easier handling, it offers further aids, such as:
            - a method to calculate available moves
            - a method to perform a move for simulating future game states

       The game server sends a new copy of the `GameState` to both participating players after each completed move,
       describing the then current state.
       """

    def __init__(self, board: Board, turn: int, first_team: Team, second_team: Team, last_move: Optional[Move]):
        """
        Creates a new `GameState` with the given parameters.

        Args:
            board: The board of the game.
            turn: The turn number of the game.
            first_team: The team_enum that has the first turn.
            second_team: The team_enum that has the second turn.
            last_move: The last move made.
        """
        self.board = board
        self.turn = turn
        self.first_team = first_team
        self.second_team = second_team
        self.last_move = last_move

    @property
    def round(self):
        return int((self.turn + 1) / 2)

    @property
    def current_team(self):
        return self.current_team_from_turn(self.turn)

    @property
    def other_team(self):
        return self.current_team.opponent

    @property
    def current_pieces(self):
        return self.current_team.get_penguins()

    @property
    def possible_moves(self):
        return self._get_possible_moves(self.current_team)

    def _get_possible_moves(self, current_team: Optional[Team]) -> List[Move]:
        """
        Gets all possible moves for the current team.
        That includes all possible moves from all Fields that are not occupied by a penguin from that team.

        :param current_team: The team to get the possible moves for.
        :return: A list of all possible moves from the current player's turn.
        """
        current_team = current_team or self.current_team
        moves = []

        if not current_team:
            return moves

        if len(self.board.get_teams_penguins(current_team.name)) < 4:
            for x in range(self.board.width()):
                for y in range(self.board.height()):
                    field = self.board.get_field(CartesianCoordinate(x, y).to_hex())
                    if not field.is_occupied() and field.get_fish() == 1:
                        moves.append(
                            Move(team_enum=current_team.name, from_value=None,
                                 to_value=CartesianCoordinate(x, y).to_hex()))
        else:
            for piece in self.board.get_teams_penguins(current_team.name):
                moves.extend(self.board.possible_moves_from(piece.coordinate, current_team.name))
        return moves

    def current_team_from_turn(self, turn: int) -> Team:
        """
        Calculates the current team from the turn number and available moves.

        :return: The team that has the current turn.
        """
        possible_moves_first = self._get_possible_moves(self.first_team)
        possible_moves_second = self._get_possible_moves(self.second_team)
        if turn % 2 == 0:
            return self.first_team if possible_moves_first else self.second_team if possible_moves_second else None
        else:
            return self.second_team if possible_moves_second else self.first_team if possible_moves_first else None

    def perform_move(self, move: Move) -> 'GameState':
        """
        Performs the given move on the current game state.

        Args:
            move: The move that has to be performed.

        Returns:
            GameState: The new state of the game after the move.
        """
        if self.is_valid_move(move) and self.current_team.name == move.team_enum:
            new_board = self.board.move(move)
            new_first_team: Team = pickle.loads(pickle.dumps(self.first_team, protocol=-1))
            new_second_team: Team = pickle.loads(pickle.dumps(self.second_team, protocol=-1))
            if self.current_team.name == TeamEnum.ONE:
                self._update_team(new_first_team, move, new_board)
            else:
                self._update_team(new_second_team, move, new_board)
            new_first_team.opponent = new_second_team
            new_second_team.opponent = new_first_team
            new_turn = self.turn + 1
            new_last_move = move
            return GameState(board=new_board, turn=new_turn, first_team=new_first_team, second_team=new_second_team,
                             last_move=new_last_move)
        else:
            logging.error(f"Performed invalid move while simulating: {move}")
            raise ValueError(f"Invalid move attempted: {move}")

    def _update_team(self, team: Team, move: Move, new_board: Board) -> None:
        """
        Helper function to update the given team when a move is performed.

        Args:
            team: The team that will be updated.
            move: The move that was performed.
            new_board: The updated board.
        """
        team.moves.append(move)
        adding_fish = self.board.get_field(move.to_value).get_fish()
        new_penguin = new_board.get_field(move.to_value).penguin
        teams_penguin = next(filter(lambda x: x.coordinate == move.from_value, team.penguins), None)
        if teams_penguin:
            teams_penguin.coordinate = new_penguin.coordinate
        else:
            team.penguins.append(new_penguin)
        team.fish += adding_fish

    def is_valid_move(self, move: Move) -> bool:
        """
        Checks if the given move is valid.

        :param move: The move to check.
        :return: True if the move is valid, False otherwise.
        """
        return move in self.possible_moves

    def opponent(self, team: Optional[Team] = None) -> Team:
        """
        Returns the opponent team of the current team.

        Returns:
            Team: The team which is the opponent of the current team.
        """
        team = team or self.current_team
        return team.opponent

    def __repr__(self):
        return f"GameState(turn={self.turn}, round={self.round}, first_team={self.first_team}, " \
               f"second_team={self.second_team}, last_move={self.last_move}, current_team={self.current_team})"
