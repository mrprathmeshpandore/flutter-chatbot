import 'package:flutter/material.dart';
import 'growth_screen.dart';

class QuizResultScreen extends StatelessWidget {
  final int score;
  final int total;
  final double? percentage;
  final List<dynamic>? details;
  final String token;

  const QuizResultScreen({
    super.key,
    required this.score,
    required this.total,
    this.percentage,
    this.details,
    this.token = '',
  });

  @override
  Widget build(BuildContext context) {
    final safeTotal = total < 0 ? 0 : total;
    final safeScore = score.clamp(0, safeTotal);
    final percent = percentage != null
        ? percentage!.round()
        : safeTotal == 0
            ? 0
            : (safeScore / safeTotal * 100).round();

    return Scaffold(
      backgroundColor: const Color(0xFFF8F7FF),
      appBar: AppBar(
        backgroundColor: const Color(0xFFF8F7FF),
        elevation: 0,
        title: const Text(
          'Quiz Results',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFFF1EFFF), Color(0xFFFBF9FF), Color(0xFFEFF8FF)],
          ),
        ),
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(22),
            child: Column(
              children: [
                const CircleAvatar(
                  radius: 58,
                  backgroundColor: Color(0xFF8D75E8),
                  child: Icon(
                    Icons.emoji_events_rounded,
                    color: Colors.white,
                    size: 55,
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  percent >= 80
                      ? 'Amazing work!'
                      : percent >= 60
                          ? 'Nice progress!'
                          : 'Keep going!',
                  style: const TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Every question is a step forward.',
                  style: TextStyle(color: Color(0xFF85859A)),
                ),
                const SizedBox(height: 25),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: const Color(0xFFEAE8F5)),
                  ),
                  child: Column(
                    children: [
                      Text(
                        '$score / $total',
                        style: const TextStyle(
                          color: Color(0xFF5965E8),
                          fontSize: 40,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      Text(
                        '$percent% score',
                        style: const TextStyle(color: Color(0xFF85859A)),
                      ),
                      const SizedBox(height: 18),
                      LinearProgressIndicator(
                        value: total == 0 ? 0 : score / total,
                        minHeight: 8,
                        valueColor: const AlwaysStoppedAnimation(
                          Color(0xFF5965E8),
                        ),
                      ),
                      const SizedBox(height: 20),
                      Row(
                        children: [
                          Expanded(
                            child: _stat('Correct', '$score', Colors.green),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _stat(
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

                if (details != null && details!.isNotEmpty) ...[
                  const SizedBox(height: 22),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'QUESTION BREAKDOWN',
                      style: const TextStyle(
                        fontSize: 11,
                        letterSpacing: 1.2,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF85859A),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  ...details!.map((detail) {
                    final d = detail is Map
                        ? Map<String, dynamic>.from(detail)
                        : <String, dynamic>{};
                    final isCorrect = d['is_correct'] == true;
                    final qText = d['question_text']?.toString() ?? '';
                    final explanation = d['explanation']?.toString() ?? '';

                    return Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(
                          color: isCorrect
                              ? Colors.green.withValues(alpha: 0.3)
                              : Colors.orange.withValues(alpha: 0.3),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                isCorrect
                                    ? Icons.check_circle_rounded
                                    : Icons.cancel_rounded,
                                color: isCorrect ? Colors.green : Colors.orange,
                                size: 20,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  qText,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    fontSize: 13,
                                    color: Color(0xFF25252B),
                                  ),
                                ),
                              ),
                            ],
                          ),
                          if (explanation.isNotEmpty) ...[
                            const SizedBox(height: 8),
                            Text(
                              explanation,
                              style: const TextStyle(
                                fontSize: 11,
                                color: Color(0xFF85859A),
                                height: 1.45,
                              ),
                            ),
                          ],
                        ],
                      ),
                    );
                  }),
                ],

                const SizedBox(height: 22),
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton.icon(
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const GrowthScreen(),
                        settings: RouteSettings(arguments: token),
                      ),
                    ),
                    icon: const Icon(Icons.insights_rounded),
                    label: const Text('View my growth'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF5965E8),
                      foregroundColor: Colors.white,
                    ),
                  ),
                ),
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Back'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _stat(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .08),
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
            style: const TextStyle(color: Color(0xFF85859A), fontSize: 12),
          ),
        ],
      ),
    );
  }
}
