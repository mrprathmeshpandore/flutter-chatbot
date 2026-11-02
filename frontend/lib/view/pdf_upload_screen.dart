import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:mind_ai/const/api_constants.dart';

class PdfUploadScreen extends StatefulWidget {
  const PdfUploadScreen({super.key});

  @override
  State<PdfUploadScreen> createState() => _PdfUploadScreenState();
}

class _PdfUploadScreenState extends State<PdfUploadScreen> {
  PlatformFile? selectedFile;
  bool isUploading = false;
  double uploadProgress = 0;

  static const Color primary = Color(0xFF5965E8);

  Future<void> pickPdf() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
        withData: true,
      );

      if (result == null || result.files.isEmpty) return;

      final file = result.files.first;

      if (file.bytes == null) {
        showMessage('Could not read the selected PDF.');
        return;
      }

      setState(() {
        selectedFile = file;
        uploadProgress = 0;
      });
    } catch (e) {
      showMessage('Could not select PDF: $e');
    }
  }

  Future<void> uploadPdf() async {
    final file = selectedFile;

    if (file == null || file.bytes == null) {
      showMessage('Please select a PDF first.');
      return;
    }

    final token = ModalRoute.of(context)?.settings.arguments;

    if (token is! String || token.isEmpty) {
      showMessage('Login token missing. Please log in again.');
      return;
    }

    setState(() {
      isUploading = true;
      uploadProgress = 0;
    });

    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('${ApiConstants.baseUrl}/pdf/upload'),
      );

      request.headers['Authorization'] = 'Bearer $token';

      request.files.add(
        http.MultipartFile.fromBytes('file', file.bytes!, filename: file.name),
      );

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (!mounted) return;

      if (response.statusCode == 200 || response.statusCode == 201) {
        setState(() {
          selectedFile = null;
          uploadProgress = 1;
        });

        showMessage('PDF uploaded successfully!');

        Navigator.pop(context, true);
      } else {
        String errorMessage = 'Upload failed (${response.statusCode})';

        try {
          final data = jsonDecode(response.body);
          if (data is Map && data['detail'] != null) {
            errorMessage = data['detail'].toString();
          }
        } catch (_) {
          if (response.body.isNotEmpty) {
            errorMessage = response.body;
          }
        }

        showMessage(errorMessage);
      }
    } catch (e) {
      if (mounted) {
        showMessage('Upload failed. Check your connection and try again.');
      }
    } finally {
      if (mounted) {
        setState(() {
          isUploading = false;
        });
      }
    }
  }

  void showMessage(String message) {
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
    );
  }

  String formatSize(int bytes) {
    if (bytes < 1024 * 1024) {
      return '${(bytes / 1024).toStringAsFixed(1)} KB';
    }

    return '${(bytes / (1024 * 1024)).toStringAsFixed(2)} MB';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F7FF),
      appBar: AppBar(
        title: const Text(
          'Upload PDF',
          style: TextStyle(
            fontWeight: FontWeight.w800,
            color: Color(0xFF25252B),
          ),
        ),
        backgroundColor: const Color(0xFFF8F7FF),
        elevation: 0,
        iconTheme: const IconThemeData(color: Color(0xFF25252B)),
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFFF1EFFF), Color(0xFFFBF9FF), Color(0xFFEFF8FF)],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 15),
                const Text(
                  'Your knowledge, one PDF away.',
                  style: TextStyle(
                    fontSize: 25,
                    height: 1.25,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF25252B),
                  ),
                ),
                const SizedBox(height: 9),
                const Text(
                  'Upload your study material and get ready to learn smarter.',
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.6,
                    color: Color(0xFF85859A),
                  ),
                ),
                const SizedBox(height: 30),

                InkWell(
                  onTap: isUploading ? null : pickPdf,
                  borderRadius: BorderRadius.circular(24),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 20,
                      vertical: 36,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.9),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(
                        color: primary.withValues(alpha: 0.35),
                        width: 1.5,
                      ),
                    ),
                    child: Column(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(18),
                          decoration: BoxDecoration(
                            color: const Color(0xFFECEBFF),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: const Icon(
                            Icons.picture_as_pdf_rounded,
                            size: 38,
                            color: primary,
                          ),
                        ),
                        const SizedBox(height: 20),
                        const Text(
                          'Choose a PDF file',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w800,
                            color: Color(0xFF25252B),
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Tap here to browse your files',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 12,
                            color: Color(0xFF85859A),
                          ),
                        ),
                        const SizedBox(height: 15),
                        const Text(
                          'PDF files only',
                          style: TextStyle(
                            fontSize: 11,
                            color: primary,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                if (selectedFile != null) ...[
                  const SizedBox(height: 20),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: const Color(0xFFEAE8F5)),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.picture_as_pdf_rounded,
                          size: 32,
                          color: primary,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                selectedFile!.name,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              const SizedBox(height: 5),
                              Text(
                                formatSize(selectedFile!.size),
                                style: const TextStyle(
                                  fontSize: 11,
                                  color: Color(0xFF85859A),
                                ),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          onPressed: isUploading
                              ? null
                              : () {
                                  setState(() {
                                    selectedFile = null;
                                  });
                                },
                          icon: const Icon(Icons.close_rounded),
                        ),
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 25),

                if (isUploading) ...[
                  const LinearProgressIndicator(),
                  const SizedBox(height: 10),
                  const Text(
                    'Uploading your PDF...',
                    style: TextStyle(fontSize: 12, color: Color(0xFF85859A)),
                  ),
                  const SizedBox(height: 15),
                ],

                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton.icon(
                    onPressed: isUploading || selectedFile == null
                        ? null
                        : uploadPdf,
                    icon: Icon(
                      isUploading
                          ? Icons.hourglass_top_rounded
                          : Icons.cloud_upload_outlined,
                    ),
                    label: Text(
                      isUploading ? 'Uploading...' : 'Upload PDF',
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: primary,
                      foregroundColor: Colors.white,
                      disabledBackgroundColor: const Color(0xFFCBCBE0),
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(15),
                      ),
                    ),
                  ),
                ),

                const SizedBox(height: 20),

                const Center(
                  child: Text(
                    'Your learning journey starts here. ✨',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 11, color: Color(0xFF85859A)),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
