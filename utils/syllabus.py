"""
The semester: three classes, six graded sections each, four blocks per section.

A block is one segment the player can catch. A section's score is simply the
fraction of its blocks caught -- catch 2 of 4 and the section is worth 50%.
Class score is the weighted sum of its sections; the semester grade follows
CUNY's letter scale, and failing any single class fails the semester.
"""
import random

BLOCKS_PER_SECTION = 4

SECTIONS = ("hw", "projects", "lab", "midterm", "final", "participation")

# each class must total 100; the spread differs so the classes play differently
WEIGHTS = {
    "eng":  {"hw": 20, "projects": 25, "lab": 5,  "midterm": 15, "final": 25, "participation": 10},
    "cs":   {"hw": 15, "projects": 30, "lab": 20, "midterm": 10, "final": 20, "participation": 5},
    "math": {"hw": 25, "projects": 10, "lab": 10, "midterm": 20, "final": 30, "participation": 5},
}

PASS_MARK = 60.0

# CUNY undergraduate letter scale
GRADE_SCALE = (
    (93, "A",  4.0), (90, "A-", 3.7), (87, "B+", 3.3), (83, "B",  3.0),
    (80, "B-", 2.7), (77, "C+", 2.3), (73, "C",  2.0), (70, "C-", 1.7),
    (67, "D+", 1.3), (63, "D",  1.0), (60, "D-", 0.7), (0,  "F",  0.0),
)


def letter_grade(score):
    """CUNY letter and grade point for a 0-100 score."""
    for cutoff, letter, points in GRADE_SCALE:
        if score >= cutoff:
            return letter, points
    return "F", 0.0


class Syllabus:
    """Tracks which blocks were caught and turns that into a report card."""

    def __init__(self, weights=None, blocks=BLOCKS_PER_SECTION):
        self.weights = weights or WEIGHTS
        self.blocks = blocks
        self.caught = {(c, s): 0 for c in self.weights for s in self.weights[c]}
        # blocks decided so far (caught or expired), for the running grade
        self.resolved = {(c, s): 0 for c in self.weights for s in self.weights[c]}

    def build_queue(self, rng=random):
        """Every block in the semester, shuffled: the spawn order for one run."""
        queue = [(c, s)
                 for c in self.weights
                 for s in self.weights[c]
                 for _ in range(self.blocks)]
        rng.shuffle(queue)
        return queue

    @property
    def total_blocks(self):
        return sum(len(v) for v in self.weights.values()) * self.blocks

    def record(self, course, section):
        self.caught[(course, section)] += 1
        self.resolved[(course, section)] += 1

    def expire(self, course, section):
        self.resolved[(course, section)] += 1

    def section_score(self, course, section):
        """Percent for one section: blocks caught out of blocks offered."""
        return 100.0 * self.caught[(course, section)] / self.blocks

    def class_score(self, course):
        """Weighted percent for one class."""
        return sum(weight * self.section_score(course, section) / 100.0
                   for section, weight in self.weights[course].items())

    def live_section_score(self, course, section):
        """Percent over blocks decided so far; None while none have been."""
        seen = self.resolved[(course, section)]
        if not seen:
            return None
        return 100.0 * self.caught[(course, section)] / seen

    def live_class_score(self, course):
        """
        Running grade for a class: the weighted average over sections that have
        had at least one block decided. Unseen sections are left out rather than
        counted as zero, so the number reads like a real gradebook.
        """
        total = live = 0.0
        for section, weight in self.weights[course].items():
            score = self.live_section_score(course, section)
            if score is not None:
                live += weight * score / 100.0
                total += weight
        if not total:
            return None
        return 100.0 * live / total

    def failing(self):
        """Classes below the pass mark."""
        return [c for c in self.weights if self.class_score(c) < PASS_MARK]

    def semester_score(self):
        return sum(self.class_score(c) for c in self.weights) / len(self.weights)

    def report(self):
        """Rows of (course, score, letter, points), plus the summary."""
        rows = []
        for course in self.weights:
            score = self.class_score(course)
            letter, points = letter_grade(score)
            rows.append((course, score, letter, points))

        failed = self.failing()
        overall = self.semester_score()
        if failed:
            return rows, overall, "F", 0.0, failed
        letter, points = letter_grade(overall)
        return rows, overall, letter, points, failed
