import 'package:flutter/material.dart';
import 'package:mind_ai/model/pdf_model.dart';
import 'package:mind_ai/repo/learning_path_repo.dart';
import 'package:mind_ai/repo/pdf_repo.dart';
import 'package:mind_ai/view/pdf_upload_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'lesson_screen.dart';

class LearningPathScreen extends StatefulWidget {
  const LearningPathScreen({super.key});

  @override
  State<LearningPathScreen> createState() => _LearningPathScreenState();
}

class _LearningPathScreenState extends State<LearningPathScreen> {
  static const Color purple = Color(0xFF5965E8);

  String token = '';
  int? pdfId;
  String? pdfTitle;

  bool initialized = false;
  bool isLoading = true;
  String? errorMessage;

  List<PdfModel> userPdfs = [];
  Map<String, dynamic>? learningPathData;
  List<dynamic> topics = [];
  Set<String> completedTopics = {};

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    if (initialized) return;
    initialized = true;

    final args = ModalRoute.of(context)?.settings.arguments;

    if (args is String) {
      token = args;
    } else if (args is Map) {
      token = args['token']?.toString() ?? '';
      final rawPdfId = args['pdfId'];
      if (rawPdfId != null) {
        pdfId = int.tryParse(rawPdfId.toString());
      }
      pdfTitle = args['pdfTitle']?.toString();
    }

    _loadData();
  }

  Future<void> _loadData() async {
    if (token.isEmpty) {
      setState(() {
        isLoading = false;
        errorMessage = 'Login token missing. Please log in again.';
      });
      return;
    }

    setState(() {
      isLoading = true;
      errorMessage = null;
    });

    try {
      // 1. If pdfId not explicitly provided, fetch PDFs to select one
      if (pdfId == null) {
        userPdfs = await PdfRepo().getPdfs(token: token);
        if (userPdfs.isEmpty) {
          setState(() {
            isLoading = false;
            learningPathData = null;
            topics = [];
          });
          return;
        }
        pdfId = userPdfs.first.id;
        pdfTitle = userPdfs.first.title;
      }

      // 2. Load learning path from backend
      final data = await LearningPathRepo().getLearningPath(
        token: token,
        pdfId: pdfId!,
      );

      learningPathData = data;
      topics = (data['topics'] as List<dynamic>?) ?? [];

      // 3. Load completed topics from local preferences
      await _loadProgress();

      if (!mounted) return;

      setState(() {
        isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        isLoading = false;
        errorMessage = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  String get _progressKey => 'completed_topics_pdf_${pdfId ?? 0}';

  Future<void> _loadProgress() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getStringList(_progressKey) ?? [];
    completedTopics = saved.toSet();
  }

  Future<void> _saveProgress(String topicTitle) async {
    final prefs = await SharedPreferences.getInstance();
    completedTopics.add(topicTitle);
    await prefs.setStringList(_progressKey, completedTopics.toList());
    if (mounted) setState(() {});
  }

  Future<void> _openLesson(Map<String, dynamic> topic, int index) async {
    final title = topic['title']?.toString() ?? 'Lesson ${index + 1}';
    final description = topic['description']?.toString() ?? '';
    final rawKeyPoints = topic['key_points'];
    final keyPoints = rawKeyPoints is List
        ? rawKeyPoints.map((k) => k.toString()).toList()
        : <String>[];
    final estimatedMinutes =
        (topic['estimated_minutes'] as num?)?.toInt() ?? 8;
    final difficulty = topic['difficulty']?.toString() ?? 'beginner';
    final isCompleted = completedTopics.contains(title);

    final completed = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => LessonScreen(
          title: title,
          description: description,
          keyPoints: keyPoints,
          estimatedMinutes: estimatedMinutes,
          difficulty: difficulty,
          token: token,
          pdfId: pdfId,
          isCompleted: isCompleted,
        ),
      ),
    );

    if (completed == true) {
      await _saveProgress(title);
    }
  }

  Future<void> _openUpload() async {
    final uploaded = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => const PdfUploadScreen(),
        settings: RouteSettings(arguments: token),
      ),
    );

    if (uploaded == true && mounted) {
      pdfId = null;
      _loadData();
    }
  }

  @override
  Widget build(BuildContext context) {
    final totalTopics = topics.length;
    final completedCount =
        topics.where((t) => completedTopics.contains(t['title'])).length;
    final progress = totalTopics == 0 ? 0.0 : completedCount / totalTopics;

    return Scaffold(
      backgroundColor: const Color(0xFFF8F7FF),
      appBar: AppBar(
        backgroundColor: const Color(0xFFF8F7FF),
        elevation: 0,
        title: Text(
          pdfTitle != null ? 'Roadmap: $pdfTitle' : 'Learning Path',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh Learning Path',
            onPressed: _loadData,
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
            ? Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: const [
                    CircularProgressIndicator(color: purple),
                    SizedBox(height: 16),
                    Text(
                      'Analyzing document & generating roadmap...',
                      style: TextStyle(
                        color: Color(0xFF85859A),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              )
            : errorMessage != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(
                            Icons.error_outline_rounded,
                            size: 48,
                            color: purple,
                          ),
                          const SizedBox(height: 14),
                          Text(
                            errorMessage!,
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                              color: Color(0xFF25252B),
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton.icon(
                            onPressed: _loadData,
                            icon: const Icon(Icons.refresh_rounded),
                            label: const Text('Try Again'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: purple,
                              foregroundColor: Colors.white,
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                : topics.isEmpty
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(28),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(
                                Icons.folder_open_rounded,
                                size: 54,
                                color: purple,
                              ),
                              const SizedBox(height: 16),
                              const Text(
                                'No PDFs uploaded yet',
                                style: TextStyle(
                                  fontSize: 19,
                                  fontWeight: FontWeight.w800,
                                  color: Color(0xFF25252B),
                                ),
                              ),
                              const SizedBox(height: 8),
                              const Text(
                                'Upload a PDF to generate a structured AI learning roadmap.',
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Color(0xFF85859A),
                                  height: 1.5,
                                ),
                              ),
                              const SizedBox(height: 20),
                              ElevatedButton.icon(
                                onPressed: _openUpload,
                                icon: const Icon(Icons.cloud_upload_outlined),
                                label: const Text('Upload PDF'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: purple,
                                  foregroundColor: Colors.white,
                                ),
                              ),
                            ],
                          ),
                        ),
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
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Icon(
                                  Icons.auto_awesome,
                                  color: Colors.white,
                                  size: 30,
                                ),
                                const SizedBox(height: 16),
                                Text(
                                  learningPathData?['title']?.toString() ??
                                      'Your personal roadmap',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 21,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  learningPathData?['overview']?.toString() ??
                                      'Learn smarter, one step at a time.',
                                  style: const TextStyle(
                                    color: Colors.white70,
                                    fontSize: 12,
                                    height: 1.5,
                                  ),
                                ),
                                const SizedBox(height: 20),
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(20),
                                  child: LinearProgressIndicator(
                                    value: progress,
                                    minHeight: 7,
                                    backgroundColor: const Color(0x55FFFFFF),
                                    valueColor: const AlwaysStoppedAnimation(
                                      Colors.white,
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  '${(progress * 100).round()}% completed ($completedCount / $totalTopics topics)',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 25),
                          const Text(
                            'YOUR LEARNING JOURNEY',
                            style: TextStyle(
                              color: Color(0xFF85859A),
                              fontSize: 11,
                              letterSpacing: 1.2,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 14),
                          ...topics.asMap().entries.map((entry) {
                            final idx = entry.key;
                            final topic = entry.value as Map<String, dynamic>;
                            final topicTitle =
                                topic['title']?.toString() ?? 'Topic ${idx + 1}';
                            final duration =
                                '${topic['estimated_minutes'] ?? 30} min';
                            final isCompleted =
                                completedTopics.contains(topicTitle);
                            final topicId =
                                (idx + 1).toString().padLeft(2, '0');

                            return Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: InkWell(
                                borderRadius: BorderRadius.circular(20),
                                onTap: () => _openLesson(topic, idx),
                                child: Container(
                                  padding: const EdgeInsets.all(16),
                                  decoration: BoxDecoration(
                                    color: Colors.white,
                                    borderRadius: BorderRadius.circular(20),
                                    border: Border.all(
                                      color: const Color(0xFFEAE8F5),
                                    ),
                                  ),
                                  child: Row(
                                    children: [
                                      CircleAvatar(
                                        backgroundColor:
                                            const Color(0xFFECEBFF),
                                        child: Text(
                                          topicId,
                                          style: const TextStyle(
                                            color: purple,
                                            fontWeight: FontWeight.w800,
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 13),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              topicTitle,
                                              style: const TextStyle(
                                                fontWeight: FontWeight.w800,
                                                color: Color(0xFF25252B),
                                              ),
                                            ),
                                            const SizedBox(height: 5),
                                            Text(
                                              '$duration • ${topic['difficulty'] ?? 'beginner'}',
                                              style: const TextStyle(
                                                color: Color(0xFF85859A),
                                                fontSize: 12,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                      Icon(
                                        isCompleted
                                            ? Icons.check_circle
                                            : Icons.arrow_forward_ios_rounded,
                                        size: 18,
                                        color: isCompleted
                                            ? Colors.green
                                            : const Color(0xFF85859A),
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
    );
  }
}
