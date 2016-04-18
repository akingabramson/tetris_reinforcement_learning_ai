import random, sys

from collections import defaultdict
from copy import deepcopy
from tetris_utils import *

class TetrisReinforcementLearner:
    def __init__(self, tetris_game):
        self.tetris_game = tetris_game

        self.episodes_to_display = 5
        self.episodes_to_train = 20
        self.current_episode = 0
        self.weights = defaultdict(lambda: 0)
        self.discount = 0.9
        self.initial_alpha = 0.005
        self.alpha = self.initial_alpha
        self.initial_epsilon = 0.0
        self.epsilon = self.initial_epsilon

    def train(self):
        self.play()

    def play(self):
        self.tetris_game.start_game()
        self.tetris_game.run(self, True)

    def play_trained_game(self):
        self.tetris_game.start_game()
        self.tetris_game.run(self, True)

    def quit(self):
        self.tetris_game.quit()
        sys.exit()

    def capture_state_attributes(self, game):
        return {
            "board": deepcopy(game.board),
            "stone": game.stone,
            "next_stone": game.next_stone,
            "stone_x": game.stone_x,
            "stone_y": game.stone_y,
            "gameover": game.gameover
        }

    def print_weights(self):
        for feature, weight in self.weights.iteritems():
            print "{0}: {1}".format(feature, weight)
        print ""

    def next_episode(self):
        self.current_episode += 1
        self.epsilon = self.initial_epsilon * (1 - self.current_episode / self.episodes_to_train)
        self.alpha = self.alpha - (self.initial_alpha / self.episodes_to_train)

        print "After {0} episodes, score is {1}".format(self.current_episode, self.tetris_game.score)
        print "{0} lines cleared".format(self.tetris_game.lines)

        self.print_weights()

        if self.current_episode > (self.episodes_to_train + self.episodes_to_display):
            return self.quit()
        elif self.current_episode >= self.episodes_to_train:
            self.alpha = 0
            self.epsilon = 0
            return self.play_trained_game()
        else:
            return self.play()

    def move_is_legal(self, delta_x, state):
        new_x = state['stone_x'] + delta_x
        cols = len(state['board'][0])

        within_left_border = new_x >= 0
        within_right_border = new_x <= cols - len(state['stone'][0])
        collision = check_collision(state['board'],
                                       state['stone'],
                                       (new_x, state['stone_y']))

        return within_left_border and within_right_border and not collision

    def move_to_next_stone(self, state):
        state["stone"] = state["next_stone"]
        state["next_stone"] = None

        # reset x and y
        columns = len(state["board"][0])
        stone_length = len(state["stone"][0])

        state["stone_x"] = int(columns / 2 - stone_length / 2)
        state["stone_y"] = 0

    def get_legal_move_sequences(self, state):
        delta_x = 0
        legal_move_sequences = []

        while delta_x > -1 * len(state['board'][0]):
            if self.move_is_legal(delta_x, state):
                legal_move_sequences.append([delta_x])
                delta_x -= 1
            else:
                break

        delta_x = 1

        while delta_x < len(state['board'][0]):
            if self.move_is_legal(delta_x, state):
                legal_move_sequences.append([delta_x])
                delta_x += 1
            else:
                break

        return legal_move_sequences

    def turn_deltas_to_sequences(self, legal_move_sequences, rotations):
        sequences = []
        sequence_start = ["UP"] * rotations

        for delta in legal_move_sequences:
            if delta == 0:
                sequences.append(sequence_start + ["CONTINUE"])
                continue

            direction = "LEFT" if delta < 0 else "RIGHT"
            sequence = sequence_start + ([direction] * abs(delta))
            sequences.append(sequence)

        #If you're pinned or creating a row
        if len(sequences) == 0: sequences = [["CONTINUE"]]

        return sequences

    def get_move_sequences_for_each_rotation(self, state):
        move_sequences = []
        current_state = state

        rotations = 0
        while rotations < 4:
            move_sequences_at_rotation = self.get_legal_move_sequences(current_state)

            for msar_idx, move_sequence_at_rotation in enumerate(move_sequences_at_rotation):
                move_sequences_at_rotation[msar_idx] = ["UP"] * rotations + move_sequence_at_rotation

            move_sequences += move_sequences_at_rotation
            current_state = self.copy_state(current_state)
            self.rotate(current_state)
            rotations += 1

        return move_sequences

    def translate_moves_into_actions(self, move_sequences):
        for ms_idx, move_sequence in enumerate(move_sequences):
            action_sequence = []

            for move in move_sequence:
                if isinstance(move, basestring):
                    action_sequence += [move]
                    continue

                if move == 0:
                    action_sequence += ["CONTINUE"]
                    continue

                direction = "LEFT" if move < 0 else "RIGHT"
                action_sequence += [direction] * abs(move)

            move_sequences[ms_idx] = action_sequence

        return move_sequences


    def get_legal_action_sequences(self, state):
        move_sequences = self.get_move_sequences_for_each_rotation(state)
        legal_action_sequences = self.translate_moves_into_actions(move_sequences)
        if not legal_action_sequences: legal_action_sequences = [["CONTINUE"]]

        return legal_action_sequences

    def square_is_zero(self, square):
        square == 0

    def prune_action_sequence(self, action_sequence):
        pruned_action_sequence = []

        for action in action_sequence:
            if action == "NEXT_STONE": break
            pruned_action_sequence.append(action)

        return pruned_action_sequence

    def get_top_n_q_value_pairs(self, state, shuffled_action_sequences, n):
        top_n_q_value_pairs = []

        for action_sequence in shuffled_action_sequences:
            q_value = self.get_q_value(state, action_sequence)

            if len(top_n_q_value_pairs) < n:
                top_n_q_value_pairs.append([q_value, action_sequence])
                top_n_q_value_pairs.sort(key=lambda q_v_p: q_v_p[0], reverse=True)
            else:
                if q_value > top_n_q_value_pairs[-1][0]:
                    top_n_q_value_pairs.append([q_value, action_sequence])
                    top_n_q_value_pairs.sort(key=lambda q_v_p: q_v_p[0], reverse=True)
                    top_n_q_value_pairs.pop()

        return top_n_q_value_pairs

    def create_lookahead_sequences(self, state, top_n_q_value_pairs):
        lookahead_sequences = []

        for q_value_pair in top_n_q_value_pairs:
            action_sequence = q_value_pair[1]
            successor_state = self.get_successor_state(state, action_sequence)
            legal_action_sequences = self.get_legal_action_sequences(successor_state)
            for legal_action_sequence in legal_action_sequences:
                lookahead_sequence = action_sequence + ["NEXT_STONE"] + legal_action_sequence
                lookahead_sequences.append(lookahead_sequence)

        return lookahead_sequences

    def get_top_q_value_pair(self, state, action_sequences):
        top_5_q_value_pairs = self.get_top_n_q_value_pairs(state, action_sequences, 10)
        lookahead_sequences = self.create_lookahead_sequences(state, top_5_q_value_pairs)
        top_lookahead_q_value_pairs = self.get_top_n_q_value_pairs(state, lookahead_sequences, 1)

        return top_lookahead_q_value_pairs[0]

    def split_action_sequence(self, action_sequence):
        first_stone_action_sequence = []
        second_stone_action_sequence = []

        current_action_sequence = first_stone_action_sequence

        for action in action_sequence:
            if action == "NEXT_STONE":
                current_action_sequence = second_stone_action_sequence
            else:
                current_action_sequence.append(action)

        return (first_stone_action_sequence, second_stone_action_sequence)



    def get_action_sequence(self, state):
        if state["gameover"]: return self.next_episode()

        legal_action_sequences = self.get_legal_action_sequences(state)
        shuffled_action_sequences = random.sample(legal_action_sequences, len(legal_action_sequences))
        top_q_value_pair = self.get_top_q_value_pair(state, shuffled_action_sequences)

        best_action_sequence = top_q_value_pair[1]

        return self.prune_action_sequence(best_action_sequence)

    def get_max_q_value(self, state):
        legal_action_sequences = self.get_legal_action_sequences(state)
        top_q_value_pair = self.get_top_q_value_pair(state, legal_action_sequences)
        max_q_value = top_q_value_pair[0]

        return max_q_value

    def get_q_value(self, state, action_sequence):
        q_value = 0

        successor_state = self.get_successor_state(state, action_sequence)
        features = self.extract_features(state, successor_state)

        for feature, value in features.iteritems():
            q_value += self.weights[feature] * value

        return q_value

    def extract_features(self, state, successor_state):
        old_pile_height = self.get_pile_height(state)
        new_pile_height = self.get_pile_height(successor_state)
        change_in_pile_height = new_pile_height - old_pile_height

        old_holes = self.get_holes(state)
        new_holes = self.get_holes(successor_state)
        change_in_holes = new_holes - old_holes

        old_contours = self.get_contours(state)
        new_contours = self.get_contours(successor_state)
        change_in_contours = new_contours - old_contours

        features = {
            "CHANGE_IN_PILE_HEIGHT": change_in_pile_height,
            "CHANGE_IN_HOLES": change_in_holes,
            "CHANGE_IN_CONTOURS": change_in_contours
        }

        return features

    def get_contours(self, state):
        board = state["board"]
        total_contours = 0

        column_height = self.get_column_pile_height(board, 0)

        for col_idx in xrange(1, len(board[0])):
            next_column_height = self.get_column_pile_height(board, col_idx)
            height_difference = abs(next_column_height - column_height)
            column_height = next_column_height
            total_contours += height_difference


        return total_contours

    def get_column_pile_height(self, board, col_index):
        board_height = len(board) - 1
        height = 0
        pile_height = 0

        while height < board_height:
            row = board[height]

            if self.row_has_piece([row[col_index]]):
                pile_height = board_height - height
                break;
            height += 1

        return pile_height


    def get_maximum_cell_height_sum(self, state):
        if hasattr(self, "maximum_cell_height"):
            return self.maximum_cell_height
        else:
            board = state['board']
            row_index = 0
            cell_height = 0

            while row_index < len(board) - 1:
                cell_height += len(board) - 1 - row_index
                row_index += 1

            self.maximum_cell_height = cell_height * len(board[0])
            return self.maximum_cell_height


    def get_normalized_height_weighted_cells(self, state):
        return float(self.get_height_weighted_cells(state)) / float(self.get_maximum_cell_height_sum(state))

    def get_height_weighted_cells(self, state):
        copied_state = self.copy_state(state)
        self.drop_stone(copied_state)

        board = copied_state['board']
        height_weighted_cells = 0

        for row_index, row in enumerate(board):
            if row_index + 1 == len(board): continue
            height_weighted_value = len(board) - 1 - row_index

            for col_index, square in enumerate(row):
                if square > 0: height_weighted_cells += height_weighted_value

        return height_weighted_cells



    def get_holes_at_square(self, board, row_index, col_index):
        row_index += 1
        holes_at_square = 1

        while row_index < len(board) - 1:
            if board[row_index][col_index] == 0:
                holes_at_square += 1
                row_index += 1
            else:
                break

        return holes_at_square

    def get_holes(self, state):
        board = state['board']
        holes = 0

        for row_index, row in enumerate(board):
            if row_index == 0: continue
            for col_index, square in enumerate(row):
                if square == 0 and board[row_index - 1][col_index] > 0:
                    holes += self.get_holes_at_square(board, row_index, col_index)

        return holes

    def get_normalized_pile_height_if_dropped(self, state):
        height = self.get_pile_height_if_dropped(state)
        return height


    def get_pile_height_if_dropped(self, state):
        copied_state = self.copy_state(state)
        self.drop_stone(copied_state)

        pile_height = self.get_pile_height(copied_state)

        return pile_height

    def row_has_piece(self, row):
        return [square for square in row if square > 0]

    def get_pile_height(self, state):
        board = state["board"]
        pile_height = 0

        for row_index, row in enumerate(board):
            if self.row_has_piece(row):
                pile_height = len(board) - 1 - row_index
                break

        return pile_height

    def drop_stone(self, state):
        while not check_collision(state["board"], state["stone"], (state["stone_x"], state["stone_y"])):
            state["stone_y"] += 1

        join_matrixes(state["board"], state["stone"], (state["stone_x"], state["stone_y"]))
        if state["next_stone"]: self.move_to_next_stone(state)
        board = state["board"]

        while True:
            for i, row in enumerate(board[:-1]):
                if 0 not in row:
                    state["board"] = remove_row(board, i)
                    break
            else:
                break


    def get_cleared_rows(self, state):
        copied_state = self.copy_state(state)
        offset = (copied_state["stone_x"], copied_state["stone_y"])

        joined_board = join_matrixes(copied_state["board"], copied_state["stone"], offset)

        cleared_rows = 0
        for i, row in enumerate(joined_board[:-1]):
            if 0 not in row: cleared_rows += 1

        return cleared_rows

    def get_successor_state(self, state, action_sequence):
        successor_state = self.copy_state(state)

        for action in action_sequence:
            if action == 'LEFT':
                self.move(successor_state, -1)
            elif action == 'RIGHT':
                self.move(successor_state, 1)
            elif action == 'UP':
                self.rotate(successor_state)
            elif action == 'NEXT_STONE':
                self.drop_stone(successor_state)

        self.drop_stone(successor_state)

        return successor_state

    def copy_state(self, state):
        return {
            "board": deepcopy(state["board"]),
            "stone": state["stone"],
            "next_stone": state["next_stone"],
            "stone_x": state["stone_x"],
            "stone_y": state["stone_y"],
            "gameover": state["gameover"]
        }


    def move(self, state, direction):
        new_x = state["stone_x"] + direction
        board_length = len(state["board"])
        stone_length = len(state["stone"][0])

        if new_x < 0: new_x = 0
        if new_x >= board_length - stone_length:
            new_x = board_length - stone_length
        if not check_collision(state["board"],
                               state["stone"],
                               (new_x, state["stone_y"])):
            state["stone_x"] = new_x

    def rotate(self, state):
        new_stone = rotate_clockwise(state["stone"])
        if not check_collision(state["board"],
                               new_stone,
                               (state["stone_x"], state["stone_y"])):
            state["stone"] = new_stone

    def drop(self, state):
        state["stone_y"] += 1

    def join_action_sequence(self, action_sequence):
        two_action_sequences_happened = isinstance(action_sequence[0], list)

        if two_action_sequences_happened:
            return action_sequence[0] + ["NEXT_STONE"] + action_sequence[1]
        else:
            return action_sequence

    def update(self, state, action_sequence, new_state, reward):
        action_sequence = self.join_action_sequence(action_sequence)
        old_state_value = self.get_q_value(state, action_sequence)
        new_state_max_q = self.get_max_q_value(new_state)

        new_state_value = reward + self.discount * new_state_max_q
        temporal_difference = new_state_value - old_state_value

        old_successor_state = self.get_successor_state(state, action_sequence)

        features = self.extract_features(state, old_successor_state)

        for feature, value in features.iteritems():
            new_value = temporal_difference * value
            old_weight = self.weights[feature]
            new_weight = (1 - self.alpha) * old_weight + self.alpha * new_value

            self.weights[feature] = new_weight




