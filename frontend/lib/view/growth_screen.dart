import 'package:flutter/material.dart';
import 'package:mind_ai/model/progress_summary.dart';
import 'package:mind_ai/repo/progress_repo.dart';

class GrowthScreen extends StatefulWidget {
  final String token;

  const GrowthScreen({super.key, this.token = ''});

  @override
  State<GrowthScreen> createState() => _GrowthScreenState();
}

class _GrowthScreenState extends State<GrowthScreen> {
  String token = '';
  bool initialized = false;
  bool isLoading = false;
  ProgressSummary? progressData;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    if (initialized) return;
    initialized = true;

    final args = ModalRoute.of(context)?.settings.arguments;

    if (widget.token.isNotEmpty) {
      token = widget.token;
    } else if (args is String) {
      token = args;
    } else if (args is Map) {
      token = args['token']?.toString() ?? '';
    }

    if (token.isNotEmpty) {
      _loadProgress();
    }
  }

  Future<void> _loadProgress() async {
    setState(() {
      isLoading = true;
    });

    try {
      final data = await ProgressRepo().getProgressSummary(token: token);
      if (!mounted) return;
      setState(() {
        progressData = data;
        isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final activity = [
      ('Mon', .35),
      ('Tue', .55),
      ('Wed', .42),
      ('Thu', .78),
      ('Fri', .62),
      ('Sat', .92),
      ('Sun', .70),
    ];

    final pdfCount = progressData != null ? '${progressData!.totalPdfs}' : '0';
    final quizCount =
        progressData != null ? '${progressData!.totalQuizzesTaken}' : '0';
    final avgScore =
        progressData != null ? '${progressData!.averageQuizScore}%' : '0%';
    final pathCount =
        progressData != null ? '${progressData!.learningPathsCount}' : '0';

    return Scaffold(
      backgroundColor: const Color(0xFFF8F7FF),
      appBar: AppBar(
        backgroundColor: const Color(0xFFF8F7FF),
        elevation: 0,
        title: const Text(
          'Your Growth',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
        actions: [
          if (token.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.refresh_rounded),
              tooltip: 'Refresh Growth',
              onPressed: _loadProgress,
            ),
        ],
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFFF1EFFF), Color(0xFFFBF9FF), Color(0xFFEFF8FF)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: isLoading
            ? const Center(
                child: CircularProgressIndicator(color: Color(0xFF6973F0)),
              )
            : ListView(
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
                        child: _metric(
                          'PDFs Studied',
                          pdfCount,
                          Icons.picture_as_pdf_outlined,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _metric(
                          'Quizzes Taken',
                          quizCount,
                          Icons.quiz_outlined,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _metric(
                          'Average Score',
                          avgScore,
                          Icons.insights_rounded,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _metric(
                          'Learning Paths',
                          pathCount,
                          Icons.route_outlined,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 22),
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(22),
                      border: Border.all(color: const Color(0xFFEAE8F5)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Weekly activity',
                          style: TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 5),
                        const Text(
                          'Your learning consistency this week',
                          style: TextStyle(
                            color: Color(0xFF85859A),
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 22),
                        SizedBox(
                          height: 130,
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: activity
                                .map(
                                  (day) => Expanded(
                                    child: Padding(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 4,
                                      ),
                                      child: Column(
                                        mainAxisAlignment:
                                            MainAxisAlignment.end,
                                        children: [
                                          Expanded(
                                            child: Align(
                                              alignment:
                                                  Alignment.bottomCenter,
                                              child: FractionallySizedBox(
                                                heightFactor: day.$2,
                                                child: Container(
                                                  decoration: BoxDecoration(
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                      8,
                                                    ),
                                                    gradient:
                                                        const LinearGradient(
                                                      begin: Alignment
                                                          .bottomCenter,
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
                                              color: Color(0xFF85859A),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                )
                                .toList(),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(18),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: const Color(0xFFEAE8F5)),
                    ),
                    child: const Row(
                      children: [
                        Icon(
                          Icons.tips_and_updates_outlined,
                          color: Color(0xFF5965E8),
                          size: 27,
                        ),
                        SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Your next goal\nStudy for 20 minutes tomorrow to keep your streak going.',
                            style: TextStyle(
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
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFEAE8F5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: const Color(0xFF5965E8), size: 24),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: const TextStyle(fontSize: 11, color: Color(0xFF85859A)),
          ),
        ],
      ),
    );
  }
}
