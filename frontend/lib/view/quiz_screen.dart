import 'package:flutter/material.dart';
import 'package:mind_ai/repo/pdf_repo.dart';
import 'package:mind_ai/repo/quiz_repo.dart';
import 'package:mind_ai/view/pdf_upload_screen.dart';
import 'quiz_result_screen.dart';

class QuizScreen extends StatefulWidget {
  final String token;
  final int? pdfId;
  final int? quizId;

  const QuizScreen({
    super.key,
    this.token = '',
    this.pdfId,
    this.quizId,
  });

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  String token = '';
  int? pdfId;
  int? quizId;
  String quizTitle = 'Quick Quiz';

  bool initialized = false;
  bool isLoading = true;
  bool isSubmitting = false;
  String? errorMessage;

  int current = 0;
  final Map<int, int> answers = {};
  List<Map<String, dynamic>> questions = [];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    if (initialized) return;
    initialized = true;

    final args = ModalRoute.of(context)?.settings.arguments;

    if (widget.token.isNotEmpty) {
      token = widget.token;
    }
    if (widget.pdfId != null) {
      pdfId = widget.pdfId;
    }
    if (widget.quizId != null) {
      quizId = widget.quizId;
    }

    if (args is String && args.isNotEmpty) {
      token = args;
    } else if (args is Map) {
      final argToken = args['token']?.toString();
      if (argToken != null && argToken.isNotEmpty) {
        token = argToken;
      }
      final rawPdfId = args['pdfId'];
      if (rawPdfId != null) {
        pdfId = int.tryParse(rawPdfId.toString()) ?? pdfId;
      }
      final rawQuizId = args['quizId'];
      if (rawQuizId != null) {
        quizId = int.tryParse(rawQuizId.toString()) ?? quizId;
      }
    }

    _loadQuiz();
  }

  Future<void> _loadQuiz() async {
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
      answers.clear();
      current = 0;
    });

    try {
      // Step 1: Check PDF Availability
      int targetPdfId;

      if (pdfId != null) {
        targetPdfId = pdfId!;
      } else {
        final userPdfs = await PdfRepo().getPdfs(token: token);

        if (userPdfs.isEmpty) {
          if (!mounted) return;

          setState(() {
            isLoading = false;
            questions = [];
          });
          return;
        }

        targetPdfId = userPdfs.first.id;
      }

      // Step 2: Generate New Quiz
      final generated = await QuizRepo().generateQuiz(
        token: token,
        pdfId: targetPdfId,
        numQuestions: 5,
        difficulty: 'medium',
      );

      // Step 3: Populate Quiz
      _populateQuiz(generated);
    } catch (e) {
      if (!mounted) return;

      setState(() {
        isLoading = false;
        errorMessage = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  void _populateQuiz(Map<String, dynamic> quizData) {
    if (!mounted) return;

    final rawQuestions = quizData['questions'] as List<dynamic>? ?? [];
    final parsedQuestions = <Map<String, dynamic>>[];

    for (final item in rawQuestions) {
      if (item is Map) {
        final qMap = Map<String, dynamic>.from(item);
        final rawOptions = qMap['options'];
        final optionsList = rawOptions is List
            ? rawOptions.map((opt) => opt?.toString() ?? '').toList()
            : <String>[];

        parsedQuestions.add({
          'id': int.tryParse(qMap['id']?.toString() ?? '') ?? 0,
          'question_text': qMap['question_text']?.toString() ?? '',
          'options': optionsList,
        });
      }
    }

    setState(() {
      quizId = int.tryParse(quizData['id']?.toString() ?? '');
      final parsedPdfId = int.tryParse(quizData['pdf_id']?.toString() ?? '');
      if (parsedPdfId != null) {
        pdfId = parsedPdfId;
      }
      quizTitle = quizData['title']?.toString() ?? 'Quick Quiz';
      questions = parsedQuestions;
      isLoading = false;
    });
  }

  Future<void> nextQuestion() async {
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

    // Last question - Submit to backend
    if (quizId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Quiz ID missing, unable to submit.')),
      );
      return;
    }

    setState(() {
      isSubmitting = true;
    });

    try {
      final formattedAnswers = answers.entries.map((entry) {
        final q = questions[entry.key];
        final qId = int.tryParse(q['id']?.toString() ?? '') ?? 0;
        return {
          'question_id': qId,
          'selected_option': entry.value,
        };
      }).toList();

      final result = await QuizRepo().submitQuiz(
        token: token,
        quizId: quizId!,
        answers: formattedAnswers,
      );

      if (!mounted) return;

      final score = (result['correct_answers'] as num?)?.toInt() ??
          (result['score'] as num?)?.toInt() ??
          0;
      final total = (result['total_questions'] as num?)?.toInt() ?? questions.length;
      final percentage = (result['percentage'] as num?)?.toDouble() ?? 0.0;
      final details = result['details'] as List<dynamic>?;

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => QuizResultScreen(
            score: score,
            total: total,
            percentage: percentage,
            details: details,
            token: token,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Submission failed: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          isSubmitting = false;
        });
      }
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
      _loadQuiz();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return Scaffold(
        backgroundColor: const Color(0xFFF8F7FF),
        appBar: AppBar(
          backgroundColor: const Color(0xFFF8F7FF),
          elevation: 0,
          title: Text(
            quizTitle,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
        ),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: const [
              CircularProgressIndicator(color: Color(0xFF5965E8)),
              SizedBox(height: 16),
              Text(
                'Loading questions...',
                style: TextStyle(
                  color: Color(0xFF85859A),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      );
    }

    if (errorMessage != null) {
      return Scaffold(
        backgroundColor: const Color(0xFFF8F7FF),
        appBar: AppBar(
          backgroundColor: const Color(0xFFF8F7FF),
          elevation: 0,
          title: const Text(
            'Quiz & Practice',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
        ),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.error_outline_rounded,
                  size: 48,
                  color: Color(0xFF5965E8),
                ),
                const SizedBox(height: 14),
                Text(
                  errorMessage!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 14),
                ),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: _loadQuiz,
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('Try Again'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF5965E8),
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (questions.isEmpty) {
      return Scaffold(
        backgroundColor: const Color(0xFFF8F7FF),
        appBar: AppBar(
          backgroundColor: const Color(0xFFF8F7FF),
          elevation: 0,
          title: const Text(
            'Quiz & Practice',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
        ),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.folder_open_rounded,
                  size: 54,
                  color: Color(0xFF5965E8),
                ),
                const SizedBox(height: 16),
                const Text(
                  'No quizzes available',
                  style: TextStyle(
                    fontSize: 19,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF25252B),
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Upload a PDF to automatically generate interactive practice quizzes.',
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
                    backgroundColor: const Color(0xFF5965E8),
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final q = questions[current];
    final questionText = q['question_text']?.toString() ?? '';
    final rawOptions = q['options'];
    final optionsList = rawOptions is List
        ? rawOptions.map((opt) => opt.toString()).toList()
        : <String>[];

    return Scaffold(
      backgroundColor: const Color(0xFFF8F7FF),
      appBar: AppBar(
        backgroundColor: const Color(0xFFF8F7FF),
        elevation: 0,
        title: Text(
          quizTitle,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFFF1EFFF), Color(0xFFFBF9FF), Color(0xFFEFF8FF)],
          ),
        ),
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'QUESTION ${current + 1} OF ${questions.length}',
                  style: const TextStyle(
                    color: Color(0xFF5965E8),
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text('${((current + 1) / questions.length * 100).round()}%'),
              ],
            ),
            const SizedBox(height: 12),
            LinearProgressIndicator(
              value: (current + 1) / questions.length,
              minHeight: 7,
              backgroundColor: const Color(0xFFE5E3F4),
              valueColor: const AlwaysStoppedAnimation(Color(0xFF5965E8)),
            ),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: const Color(0xFFEAE8F5)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.psychology_alt_rounded,
                    color: Color(0xFF5965E8),
                    size: 30,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    questionText,
                    style: const TextStyle(
                      fontSize: 21,
                      fontWeight: FontWeight.w800,
                      height: 1.35,
                      color: Color(0xFF25252B),
                    ),
                  ),
                  const SizedBox(height: 20),
                  ...List.generate(optionsList.length, (i) {
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
                                  ? const Color(0xFF5965E8)
                                  : const Color(0xFFEAE8F5),
                            ),
                          ),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  '${String.fromCharCode(65 + i)}. ${optionsList[i]}',
                                  style: const TextStyle(
                                    fontSize: 13,
                                    color: Color(0xFF25252B),
                                  ),
                                ),
                              ),
                              if (selected)
                                const Icon(
                                  Icons.check_circle,
                                  color: Color(0xFF5965E8),
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
            SizedBox(
              height: 52,
              child: ElevatedButton(
                onPressed: isSubmitting ? null : nextQuestion,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF5965E8),
                  foregroundColor: Colors.white,
                ),
                child: isSubmitting
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 2,
                        ),
                      )
                    : Text(
                        current < questions.length - 1
                            ? 'Next question  →'
                            : 'Submit Quiz',
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
