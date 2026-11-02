import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:syncfusion_flutter_pdfviewer/pdfviewer.dart';
import 'package:mind_ai/const/api_constants.dart';
import 'package:mind_ai/view/learning_path_screen.dart';
import 'package:mind_ai/view/quiz_screen.dart';

class PdfViewerScreen extends StatefulWidget {
  final int pdfId;
  final String title;
  final String token;

  const PdfViewerScreen({
    super.key,
    required this.pdfId,
    required this.title,
    required this.token,
  });

  @override
  State<PdfViewerScreen> createState() => _PdfViewerScreenState();
}

class _PdfViewerScreenState extends State<PdfViewerScreen> {
  late Future<Uint8List> pdfFuture;

  @override
  void initState() {
    super.initState();
    pdfFuture = loadPdf();
  }

  Future<Uint8List> loadPdf() async {
    final url = Uri.parse('${ApiConstants.baseUrl}/pdf/${widget.pdfId}/file');

    debugPrint('========== PDF DEBUG ==========');
    debugPrint('PDF REQUEST URL: $url');
    debugPrint('PDF ID: ${widget.pdfId}');
    debugPrint('BASE URL: ${ApiConstants.baseUrl}');
    debugPrint('TOKEN PRESENT: ${widget.token.isNotEmpty}');

    try {
      final response = await http.get(
        url,
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );

      debugPrint('PDF STATUS: ${response.statusCode}');
      debugPrint('PDF CONTENT TYPE: ${response.headers['content-type']}');
      debugPrint('PDF BYTES: ${response.bodyBytes.length}');

      if (response.statusCode != 200) {
        debugPrint('PDF RESPONSE BODY: ${response.body}');

        throw Exception('HTTP ${response.statusCode}: ${response.body}');
      }

      final bytes = response.bodyBytes;

      if (bytes.isEmpty) {
        throw Exception('The server returned an empty PDF file.');
      }

      // A valid PDF normally begins with the %PDF- signature.
      final headerLength = bytes.length < 5 ? bytes.length : 5;
      final signature = String.fromCharCodes(bytes.sublist(0, headerLength));

      debugPrint('PDF SIGNATURE: $signature');
      debugPrint('========== END PDF DEBUG ==========');

      if (!signature.startsWith('%PDF-')) {
        throw Exception('The server response is not a valid PDF file.');
      }

      return bytes;
    } catch (e) {
      debugPrint('PDF LOADING ERROR: $e');
      rethrow;
    }
  }

  void retryLoading() {
    setState(() {
      pdfFuture = loadPdf();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F7FF),
      appBar: AppBar(
        title: Text(
          widget.title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            color: Color(0xFF25252B),
            fontWeight: FontWeight.w700,
            fontSize: 16,
          ),
        ),
        backgroundColor: const Color(0xFFF8F7FF),
        iconTheme: const IconThemeData(color: Color(0xFF25252B)),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.auto_awesome_rounded, color: Color(0xFF5965E8)),
            tooltip: 'Ask AI Teacher',
            onPressed: () {
              Navigator.pushNamed(
                context,
                '/chatbot',
                arguments: {
                  'token': widget.token,
                  'pdfId': widget.pdfId,
                  'pdfTitle': widget.title,
                },
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.route_rounded, color: Color(0xFF159C86)),
            tooltip: 'Learning Path',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const LearningPathScreen(),
                  settings: RouteSettings(
                    arguments: {
                      'token': widget.token,
                      'pdfId': widget.pdfId,
                      'pdfTitle': widget.title,
                    },
                  ),
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.quiz_rounded, color: Color(0xFFE08A43)),
            tooltip: 'Quiz & Practice',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const QuizScreen(),
                  settings: RouteSettings(
                    arguments: {
                      'token': widget.token,
                      'pdfId': widget.pdfId,
                      'pdfTitle': widget.title,
                    },
                  ),
                ),
              );
            },
          ),
        ],
      ),
      body: FutureBuilder<Uint8List>(
        future: pdfFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircularProgressIndicator(color: Color(0xFF5965E8)),
                  SizedBox(height: 16),
                  Text('Loading your PDF...'),
                ],
              ),
            );
          }

          if (snapshot.hasError) {
            return Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.error_outline_rounded,
                      size: 48,
                      color: Color(0xFF5965E8),
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'Could not open this PDF',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF25252B),
                      ),
                    ),
                    const SizedBox(height: 10),
                    SelectableText(
                      snapshot.error.toString(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xFF666677),
                      ),
                    ),
                    const SizedBox(height: 18),
                    ElevatedButton.icon(
                      onPressed: retryLoading,
                      icon: const Icon(Icons.refresh_rounded),
                      label: const Text('Try again'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF5965E8),
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }

          final bytes = snapshot.data;

          if (bytes == null || bytes.isEmpty) {
            return const Center(child: Text('The PDF file is empty.'));
          }

          return SfPdfViewer.memory(
            bytes,
            canShowScrollHead: true,
            canShowScrollStatus: true,
          );
        },
      ),
    );
  }
}
