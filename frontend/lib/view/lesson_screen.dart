import 'package:flutter/material.dart';
import 'package:mind_ai/repo/learning_path_repo.dart';
import 'quiz_screen.dart';

class LessonScreen extends StatefulWidget {
  final String title;
  final String description;
  final List<String> keyPoints;
  final int estimatedMinutes;
  final String difficulty;
  final String token;
  final int? pdfId;
  final bool isCompleted;

  const LessonScreen({
    super.key,
    this.title = 'Understanding the basics',
    this.description =
        'Understand the important ideas, connect the concepts, and learn at your own pace.',
    this.keyPoints = const [],
    this.estimatedMinutes = 8,
    this.difficulty = 'beginner',
    this.token = '',
    this.pdfId,
    this.isCompleted = false,
  });

  @override
  State<LessonScreen> createState() => _LessonScreenState();
}

class _LessonScreenState extends State<LessonScreen> {
  String? aiExplanation;
  bool isExplaining = false;
  String? explainError;

  Future<void> _fetchAiExplanation() async {
    if (widget.token.isEmpty || widget.pdfId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('AI Explanation requires an uploaded PDF and login.'),
        ),
      );
      return;
    }

    setState(() {
      isExplaining = true;
      explainError = null;
    });

    try {
      final result = await LearningPathRepo().explainTopic(
        token: widget.token,
        pdfId: widget.pdfId!,
        topic: widget.title,
        depth: widget.difficulty,
      );

      if (!mounted) return;

      setState(() {
        aiExplanation = result['explanation']?.toString();
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        explainError = 'Could not generate explanation: $e';
      });
    } finally {
      if (mounted) {
        setState(() {
          isExplaining = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F7FF),
      appBar: AppBar(
        backgroundColor: const Color(0xFFF8F7FF),
        elevation: 0,
        title: const Text(
          'Lesson',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFFF1EFFF), Color(0xFFFBF9FF), Color(0xFFEFF8FF)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              height: 165,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(24),
                gradient: const LinearGradient(
                  colors: [Color(0xFF7978ED), Color(0xFFB6A8F5)],
                ),
              ),
              child: const Icon(
                Icons.menu_book_rounded,
                size: 72,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 22),
            Text(
              'LESSON • ${widget.estimatedMinutes} MIN READ • ${widget.difficulty.toUpperCase()}',
              style: const TextStyle(
                color: Color(0xFF5965E8),
                fontWeight: FontWeight.w800,
                fontSize: 11,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              widget.title,
              style: const TextStyle(
                fontSize: 27,
                fontWeight: FontWeight.w800,
                color: Color(0xFF25252B),
              ),
            ),
            const SizedBox(height: 12),
            Text(
              widget.description,
              style: const TextStyle(color: Color(0xFF85859A), height: 1.7),
            ),
            const SizedBox(height: 22),

            if (widget.keyPoints.isNotEmpty)
              ...widget.keyPoints.asMap().entries.map((entry) {
                final icons = [
                  Icons.lightbulb_outline,
                  Icons.account_tree_outlined,
                  Icons.summarize_outlined,
                  Icons.check_circle_outline,
                ];
                final icon = icons[entry.key % icons.length];
                return _section(
                  icon,
                  'Key Point ${entry.key + 1}',
                  entry.value,
                );
              })
            else ...[
              _section(
                Icons.lightbulb_outline,
                'Key idea',
                'Start with the main concept and understand why it matters.',
              ),
              _section(
                Icons.account_tree_outlined,
                'How it works',
                'Break the topic into smaller steps and connect each idea.',
              ),
              _section(
                Icons.summarize_outlined,
                'Quick recap',
                'Review the definition, important points, and examples.',
              ),
            ],

            const SizedBox(height: 12),

            // AI Teacher In-Depth Explanation Section
            Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(17),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFFEAE8F5)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(
                        Icons.auto_awesome_rounded,
                        color: Color(0xFF5965E8),
                        size: 24,
                      ),
                      const SizedBox(width: 10),
                      const Expanded(
                        child: Text(
                          'AI Teacher Deep-Dive',
                          style: TextStyle(
                            fontWeight: FontWeight.w800,
                            color: Color(0xFF25252B),
                            fontSize: 15,
                          ),
                        ),
                      ),
                      if (aiExplanation == null && !isExplaining)
                        TextButton.icon(
                          onPressed: _fetchAiExplanation,
                          icon: const Icon(Icons.psychology_alt_rounded, size: 16),
                          label: const Text('Explain'),
                        ),
                    ],
                  ),
                  if (isExplaining) ...[
                    const SizedBox(height: 14),
                    const Center(
                      child: Padding(
                        padding: EdgeInsets.all(12),
                        child: CircularProgressIndicator(color: Color(0xFF5965E8)),
                      ),
                    ),
                  ],
                  if (explainError != null) ...[
                    const SizedBox(height: 10),
                    Text(
                      explainError!,
                      style: const TextStyle(color: Colors.red, fontSize: 12),
                    ),
                  ],
                  if (aiExplanation != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      aiExplanation!,
                      style: const TextStyle(
                        color: Color(0xFF25252B),
                        fontSize: 13,
                        height: 1.65,
                      ),
                    ),
                  ],
                ],
              ),
            ),

            const SizedBox(height: 15),

            SizedBox(
              height: 52,
              child: ElevatedButton.icon(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const QuizScreen(),
                    settings: RouteSettings(
                      arguments: {
                        'token': widget.token,
                        'pdfId': widget.pdfId,
                      },
                    ),
                  ),
                ),
                icon: const Icon(Icons.quiz_outlined),
                label: const Text('Take quick quiz'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF5965E8),
                  foregroundColor: Colors.white,
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(15),
                  ),
                ),
              ),
            ),

            const SizedBox(height: 12),

            SizedBox(
              height: 52,
              child: OutlinedButton.icon(
                onPressed: () {
                  Navigator.pop(context, true);
                },
                icon: const Icon(Icons.check_circle_outline),
                label: const Text('Complete lesson'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _section(IconData icon, String heading, String body) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(17),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFEAE8F5)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: const Color(0xFF5965E8), size: 27),
          const SizedBox(width: 13),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  heading,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF25252B),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  body,
                  style: const TextStyle(
                    color: Color(0xFF85859A),
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
