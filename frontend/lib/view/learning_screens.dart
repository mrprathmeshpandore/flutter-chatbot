import 'package:flutter/material.dart';

const Color learningBg = Color(0xFFF8F7FF);
const Color learningPrimary = Color(0xFF5965E8);
const Color learningInk = Color(0xFF25252B);
const Color learningMuted = Color(0xFF85859A);

BoxDecoration learningCard() => BoxDecoration(
  color: Colors.white.withValues(alpha: 0.94),
  borderRadius: BorderRadius.circular(20),
  border: Border.all(color: const Color(0xFFEAE8F5)),
);

BoxDecoration learningGradient() => const BoxDecoration(
  gradient: LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFF1EFFF), Color(0xFFFBF9FF), Color(0xFFEFF8FF)],
  ),
);

Widget learningButton(
  String text,
  VoidCallback onPressed, {
  IconData icon = Icons.arrow_forward_rounded,
}) {
  return SizedBox(
    width: double.infinity,
    height: 52,
    child: ElevatedButton.icon(
      onPressed: onPressed,
      icon: Icon(icon),
      label: Text(text, style: const TextStyle(fontWeight: FontWeight.w800)),
      style: ElevatedButton.styleFrom(
        backgroundColor: learningPrimary,
        foregroundColor: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
      ),
    ),
  );
}

class LearningPathScreen extends StatelessWidget {
  const LearningPathScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final topics = [
      ('01', 'Understand the basics', '8 min', true),
      ('02', 'Explore key concepts', '12 min', true),
      ('03', 'Practice and apply', '10 min', false),
      ('04', 'Review your knowledge', '5 min', false),
    ];

    return Scaffold(
      backgroundColor: learningBg,
      appBar: AppBar(
        backgroundColor: learningBg,
        elevation: 0,
        title: const Text(
          'Learning Path',
          style: TextStyle(color: learningInk, fontWeight: FontWeight.w800),
        ),
      ),
      body: Container(
        decoration: learningGradient(),
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(25),
                gradient: const LinearGradient(
                  colors: [Color(0xFF6973F0), Color(0xFF8D75E8)],
                ),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.auto_awesome, color: Colors.white, size: 30),
                  SizedBox(height: 15),
                  Text(
                    'Your personal roadmap',
                    style: TextStyle(
                      fontSize: 23,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'Learn smarter, one step at a time.',
                    style: TextStyle(color: Colors.white70),
                  ),
                  SizedBox(height: 20),
                  LinearProgressIndicator(
                    value: 0.25,
                    minHeight: 7,
                    backgroundColor: Color(0x55FFFFFF),
                    valueColor: AlwaysStoppedAnimation(Colors.white),
                  ),
                  SizedBox(height: 9),
                  Text('25% completed', style: TextStyle(color: Colors.white)),
                ],
              ),
            ),
            const SizedBox(height: 25),
            const Text(
              'YOUR LEARNING JOURNEY',
              style: TextStyle(
                color: learningMuted,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.1,
                fontSize: 11,
              ),
            ),
            const SizedBox(height: 14),
            ...topics.map(
              (topic) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: InkWell(
                  borderRadius: BorderRadius.circular(20),
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => LessonScreen(title: topic.$2),
                    ),
                  ),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: learningCard(),
                    child: Row(
                      children: [
                        CircleAvatar(
                          radius: 23,
                          backgroundColor: const Color(0xFFECEBFF),
                          child: Text(
                            topic.$1,
                            style: const TextStyle(
                              color: learningPrimary,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                        const SizedBox(width: 13),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                topic.$2,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                  color: learningInk,
                                ),
                              ),
                              const SizedBox(height: 5),
                              Text(
                                topic.$3,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: learningMuted,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Icon(
                          topic.$4
                              ? Icons.check_circle_rounded
                              : Icons.arrow_forward_ios_rounded,
                          size: 18,
                          color: topic.$4 ? Colors.green : learningMuted,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class LessonScreen extends StatelessWidget {
  final String title;

  const LessonScreen({super.key, this.title = 'Understanding the basics'});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: learningBg,
      appBar: AppBar(
        backgroundColor: learningBg,
        elevation: 0,
        title: const Text(
          'Lesson',
          style: TextStyle(color: learningInk, fontWeight: FontWeight.w800),
        ),
      ),
      body: Container(
        decoration: learningGradient(),
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              height: 165,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(25),
                gradient: const LinearGradient(
                  colors: [Color(0xFF7978ED), Color(0xFFB6A8F5)],
                ),
              ),
              child: const Icon(
                Icons.menu_book_rounded,
                color: Colors.white,
                size: 72,
              ),
            ),
            const SizedBox(height: 23),
            const Text(
              'LESSON 01  •  8 MIN READ',
              style: TextStyle(
                color: learningPrimary,
                fontWeight: FontWeight.w800,
                fontSize: 11,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              title,
              style: const TextStyle(
                fontSize: 27,
                height: 1.2,
                fontWeight: FontWeight.w800,
                color: learningInk,
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              'Understand the important ideas, connect the concepts, '
              'and learn at your own pace.',
              style: TextStyle(color: learningMuted, height: 1.7),
            ),
            const SizedBox(height: 22),
            _lessonSection(
              Icons.lightbulb_outline_rounded,
              'Key idea',
              'Start with the main concept and understand why it matters.',
            ),
            const SizedBox(height: 12),
            _lessonSection(
              Icons.account_tree_outlined,
              'How it works',
              'Break the topic into smaller steps and connect each idea.',
            ),
            const SizedBox(height: 12),
            _lessonSection(
              Icons.summarize_outlined,
              'Quick recap',
              'Review the definition, important points, and examples.',
            ),
            const SizedBox(height: 25),
            learningButton(
              'Take quick quiz',
              () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const QuizScreen()),
              ),
              icon: Icons.quiz_outlined,
            ),
          ],
        ),
      ),
    );
  }

  Widget _lessonSection(IconData icon, String heading, String body) {
    return Container(
      padding: const EdgeInsets.all(17),
      decoration: learningCard(),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: learningPrimary, size: 27),
          const SizedBox(width: 13),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  heading,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    color: learningInk,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  body,
                  style: const TextStyle(
                    color: learningMuted,
                    fontSize: 12,
                    height: 1.6,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class QuizScreen extends StatefulWidget {
  const QuizScreen({super.key});

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  int current = 0;
  final Map<int, int> answers = {};

  final questions = const [
    (
      'What is the best way to learn a new topic?',
      [
        'Memorize every line',
        'Understand the main idea',
        'Skip examples',
        'Guess',
      ],
      1,
    ),
    (
      'Which habit helps you remember?',
      [
        'Never revise',
        'Study everything once',
        'Practice recalling',
        'Skip practice',
      ],
      2,
    ),
    (
      'What should you do with a difficult concept?',
      ['Break it into steps', 'Ignore it', 'Read faster', 'Give up'],
      0,
    ),
    (
      'Why is revision useful?',
      [
        'It adds more pages',
        'It replaces learning',
        'It wastes time',
        'It reinforces ideas',
      ],
      3,
    ),
    (
      'How can you test understanding?',
      [
        'Avoid questions',
        'Explain in your own words',
        'Skip practice',
        'Only highlight',
      ],
      1,
    ),
  ];

  void nextQuestion() {
    if (!answers.containsKey(current)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select an answer first.')),
      );
      return;
    }

    if (current < questions.length - 1) {
      setState(() => current++);
      return;
    }

    int score = 0;
    for (int i = 0; i < questions.length; i++) {
      if (answers[i] == questions[i].$3) score++;
    }

    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => QuizResultScreen(score: score, total: questions.length),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final question = questions[current];

    return Scaffold(
      backgroundColor: learningBg,
      appBar: AppBar(
        backgroundColor: learningBg,
        elevation: 0,
        title: const Text(
          'Quick Quiz',
          style: TextStyle(color: learningInk, fontWeight: FontWeight.w800),
        ),
      ),
      body: Container(
        decoration: learningGradient(),
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'QUESTION ${current + 1} OF ${questions.length}',
                  style: const TextStyle(
                    color: learningPrimary,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  '${((current + 1) / questions.length * 100).round()}%',
                  style: const TextStyle(color: learningMuted),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: LinearProgressIndicator(
                value: (current + 1) / questions.length,
                minHeight: 7,
                backgroundColor: const Color(0xFFE5E3F4),
                valueColor: const AlwaysStoppedAnimation(learningPrimary),
              ),
            ),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: learningCard(),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.psychology_alt_rounded,
                    color: learningPrimary,
                    size: 30,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    question.$1,
                    style: const TextStyle(
                      color: learningInk,
                      fontSize: 21,
                      fontWeight: FontWeight.w800,
                      height: 1.35,
                    ),
                  ),
                  const SizedBox(height: 20),
                  ...List.generate(question.$2.length, (i) {
                    final selected = answers[current] == i;

                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: InkWell(
                        onTap: () => setState(() => answers[current] = i),
                        borderRadius: BorderRadius.circular(15),
                        child: Container(
                          padding: const EdgeInsets.all(15),
                          decoration: BoxDecoration(
                            color: selected
                                ? const Color(0xFFECEBFF)
                                : const Color(0xFFFBFAFF),
                            borderRadius: BorderRadius.circular(15),
                            border: Border.all(
                              color: selected
                                  ? learningPrimary
                                  : const Color(0xFFEAE8F5),
                            ),
                          ),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  '${String.fromCharCode(65 + i)}. ${question.$2[i]}',
                                  style: const TextStyle(
                                    color: learningInk,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                              if (selected)
                                const Icon(
                                  Icons.check_circle,
                                  color: learningPrimary,
                                ),
                            ],
                          ),
                        ),
                      ),
                    );
                  }),
                ],
              ),
            ),
            const SizedBox(height: 22),
            learningButton(
              current == questions.length - 1
                  ? 'See my results'
                  : 'Next question',
              nextQuestion,
            ),
          ],
        ),
      ),
    );
  }
}

class QuizResultScreen extends StatelessWidget {
  final int score;
  final int total;

  const QuizResultScreen({super.key, this.score = 4, this.total = 5});

  @override
  Widget build(BuildContext context) {
    final percent = total == 0 ? 0 : (score / total * 100).round();
    final message = percent >= 80
        ? 'Amazing work!'
        : percent >= 60
        ? 'Nice progress!'
        : 'Keep going!';

    return Scaffold(
      backgroundColor: learningBg,
      appBar: AppBar(
        backgroundColor: learningBg,
        elevation: 0,
        title: const Text(
          'Quiz Results',
          style: TextStyle(color: learningInk, fontWeight: FontWeight.w800),
        ),
      ),
      body: Container(
        decoration: learningGradient(),
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(22),
            child: Column(
              children: [
                Container(
                  width: 115,
                  height: 115,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(
                      colors: [Color(0xFF6973F0), Color(0xFFB4A7F6)],
                    ),
                  ),
                  child: const Icon(
                    Icons.emoji_events_rounded,
                    color: Colors.white,
                    size: 55,
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  message,
                  style: const TextStyle(
                    fontSize: 28,
                    color: learningInk,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Every question is a step forward.',
                  style: TextStyle(color: learningMuted),
                ),
                const SizedBox(height: 25),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(24),
                  decoration: learningCard(),
                  child: Column(
                    children: [
                      Text(
                        '$score / $total',
                        style: const TextStyle(
                          color: learningPrimary,
                          fontSize: 40,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      Text(
                        '$percent% score',
                        style: const TextStyle(color: learningMuted),
                      ),
                      const SizedBox(height: 18),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(20),
                        child: LinearProgressIndicator(
                          value: total == 0 ? 0 : score / total,
                          minHeight: 8,
                          backgroundColor: const Color(0xFFEAE8F5),
                          valueColor: const AlwaysStoppedAnimation(
                            learningPrimary,
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),
                      Row(
                        children: [
                          Expanded(
                            child: _resultStat(
                              'Correct',
                              '$score',
                              Colors.green,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _resultStat(
                              'Review',
                              '${total - score}',
                              Colors.orange,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 22),
                learningButton(
                  'View my growth',
                  () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const GrowthScreen()),
                  ),
                  icon: Icons.insights_rounded,
                ),
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text(
                    'Back to lesson',
                    style: TextStyle(color: learningPrimary),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _resultStat(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(15),
      ),
      child: Column(
        children: [
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 23,
              fontWeight: FontWeight.w800,
            ),
          ),
          Text(
            label,
            style: const TextStyle(color: learningMuted, fontSize: 12),
          ),
        ],
      ),
    );
  }
}

class GrowthScreen extends StatelessWidget {
  const GrowthScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final activity = [
      ('Mon', 0.35),
      ('Tue', 0.55),
      ('Wed', 0.42),
      ('Thu', 0.78),
      ('Fri', 0.62),
      ('Sat', 0.92),
      ('Sun', 0.70),
    ];

    return Scaffold(
      backgroundColor: learningBg,
      appBar: AppBar(
        backgroundColor: learningBg,
        elevation: 0,
        title: const Text(
          'Your Growth',
          style: TextStyle(color: learningInk, fontWeight: FontWeight.w800),
        ),
      ),
      body: Container(
        decoration: learningGradient(),
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(24),
                gradient: const LinearGradient(
                  colors: [Color(0xFF6973F0), Color(0xFF8D75E8)],
                ),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.auto_awesome, color: Colors.white, size: 28),
                  SizedBox(height: 15),
                  Text(
                    'Look how far you’ve come!',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'Small, consistent steps lead to real progress.',
                    style: TextStyle(color: Colors.white70, height: 1.5),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _metric('Study time', '3.5 hrs', Icons.timer_outlined),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _metric('Lessons', '12', Icons.menu_book_outlined),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(child: _metric('Quizzes', '8', Icons.quiz_outlined)),
                const SizedBox(width: 12),
                Expanded(
                  child: _metric(
                    'Streak',
                    '5 days',
                    Icons.local_fire_department_outlined,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 22),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: learningCard(),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Weekly activity',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                      color: learningInk,
                    ),
                  ),
                  const SizedBox(height: 5),
                  const Text(
                    'Your learning consistency this week',
                    style: TextStyle(color: learningMuted, fontSize: 12),
                  ),
                  const SizedBox(height: 22),
                  SizedBox(
                    height: 130,
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: activity.map((day) {
                        return Expanded(
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 4),
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.end,
                              children: [
                                Expanded(
                                  child: Align(
                                    alignment: Alignment.bottomCenter,
                                    child: FractionallySizedBox(
                                      heightFactor: day.$2,
                                      child: Container(
                                        decoration: BoxDecoration(
                                          borderRadius: BorderRadius.circular(
                                            8,
                                          ),
                                          gradient: const LinearGradient(
                                            begin: Alignment.bottomCenter,
                                            end: Alignment.topCenter,
                                            colors: [
                                              Color(0xFF6973F0),
                                              Color(0xFFB4A7F6),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  day.$1,
                                  style: const TextStyle(
                                    fontSize: 10,
                                    color: learningMuted,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: learningCard(),
              child: const Row(
                children: [
                  Icon(
                    Icons.tips_and_updates_outlined,
                    color: learningPrimary,
                    size: 27,
                  ),
                  SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Your next goal\nStudy for 20 minutes tomorrow to keep your streak going.',
                      style: TextStyle(
                        color: learningInk,
                        height: 1.6,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _metric(String title, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: learningCard(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: learningPrimary, size: 24),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.w800,
              color: learningInk,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: const TextStyle(fontSize: 11, color: learningMuted),
          ),
        ],
      ),
    );
  }
}
