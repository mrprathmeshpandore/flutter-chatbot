import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:http/http.dart' as http;
import 'package:mind_ai/const/api_constants.dart';
import 'package:mind_ai/model/pdf_model.dart';
import 'package:mind_ai/repo/pdf_repo.dart';
import 'package:mind_ai/repo/user_repo.dart';

class ChatMessage {
  final String role; // 'user' or 'assistant'
  String content;
  bool isStreaming;
  List<int> sourcePages;

  ChatMessage({
    required this.role,
    required this.content,
    this.isStreaming = false,
    List<int>? sourcePages,
  }) : sourcePages = sourcePages ?? [];
}

class ChatbotScreen extends StatefulWidget {
  const ChatbotScreen({super.key});

  @override
  State<ChatbotScreen> createState() => _ChatbotScreenState();
}

class _ChatbotScreenState extends State<ChatbotScreen> {
  final UserRepo _userRepo = UserRepo();
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  final List<ChatMessage> _messages = [];

  String _token = '';
  String _userName = '';
  int? _pdfId;
  String _pdfTitle = 'AI Teacher';
  List<PdfModel> _userPdfs = [];

  bool _isLoading = false;
  bool _argumentsLoaded = false;
  http.Client? _currentClient;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    if (_argumentsLoaded) return;
    _argumentsLoaded = true;

    final arguments = ModalRoute.of(context)?.settings.arguments;

    if (arguments is String) {
      _token = arguments;
    } else if (arguments is Map) {
      _token = arguments['token']?.toString() ?? '';
      _userName = arguments['userName']?.toString() ?? '';

      final id = arguments['pdfId'];
      if (id != null) {
        _pdfId = int.tryParse(id.toString());
      }

      _pdfTitle = arguments['pdfTitle']?.toString() ?? 'AI Teacher';
    }

    if (_token.isNotEmpty) {
      _initUserContext();
      if (_pdfId == null) {
        _initPdfContext();
      }
    }
  }

  Future<void> _initUserContext() async {
    if (_token.isEmpty) return;

    // Check cached profile first
    final cached = await _userRepo.getCachedProfile();
    if (cached != null && mounted) {
      final name = cached.displayName;
      if (name.isNotEmpty && _userName.isEmpty) {
        setState(() => _userName = name);
      }
    }

    try {
      final user = await _userRepo.getProfile(token: _token);
      if (mounted && user.displayName.isNotEmpty) {
        setState(() => _userName = user.displayName);
      }
    } catch (_) {}
  }

  Future<void> _initPdfContext() async {
    if (_token.isEmpty) return;

    try {
      final pdfs = await PdfRepo().getPdfs(token: _token);
      if (!mounted) return;

      setState(() {
        _userPdfs = pdfs;
        if (_pdfId == null && pdfs.isNotEmpty) {
          _pdfId = pdfs.first.id;
          _pdfTitle = pdfs.first.title;
        }
      });
    } catch (e) {
      debugPrint('Could not load user PDFs: $e');
    }
  }

  void _showPdfSelector() {
    if (_userPdfs.isEmpty) return;

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Select Document for RAG Context',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 12),
                ..._userPdfs.map((pdf) {
                  final isSelected = pdf.id == _pdfId;
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.picture_as_pdf_rounded, color: Color(0xFF6255D9)),
                    title: Text(
                      pdf.title,
                      style: TextStyle(
                        fontWeight: isSelected ? FontWeight.w800 : FontWeight.w500,
                        color: isSelected ? const Color(0xFF6255D9) : const Color(0xFF25252B),
                      ),
                    ),
                    trailing: isSelected ? const Icon(Icons.check_circle_rounded, color: Color(0xFF6255D9)) : null,
                    onTap: () {
                      setState(() {
                        _pdfId = pdf.id;
                        _pdfTitle = pdf.title;
                      });
                      Navigator.pop(context);
                    },
                  );
                }),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  void dispose() {
    _currentClient?.close();
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _stopGeneration() {
    _currentClient?.close();
    _currentClient = null;
    if (mounted) {
      setState(() {
        _isLoading = false;
        if (_messages.isNotEmpty && _messages.last.isStreaming) {
          _messages.last.isStreaming = false;
          if (_messages.last.content.isEmpty) {
            _messages.last.content = '(Response generation stopped)';
          }
        }
      });
    }
  }

  Future<void> _sendMessage() async {
    final question = _messageController.text.trim();

    if (question.length < 2 || _isLoading) return;

    if (_token.isEmpty) {
      _showMessage('Login token missing. Please login again.');
      return;
    }

    final userMessage = ChatMessage(role: 'user', content: question);
    final assistantMessage = ChatMessage(
      role: 'assistant',
      content: '',
      isStreaming: true,
    );

    setState(() {
      _messages.add(userMessage);
      _messages.add(assistantMessage);
      _messageController.clear();
      _isLoading = true;
    });

    _scrollToBottom();

    final client = http.Client();
    _currentClient = client;

    try {
      final history = _messages
          .take(_messages.length - 2)
          .map(
            (message) => {
              'role': message.role == 'user' ? 'user' : 'model',
              'content': message.content,
            },
          )
          .toList();

      final Map<String, dynamic> requestBody = {
        'question': question,
        'history': history,
      };

      if (_pdfId != null) {
        requestBody['pdf_id'] = _pdfId;
      }

      // 1. Attempt real-time SSE stream request
      final streamUrl = Uri.parse('${ApiConstants.baseUrl}/ai/ask-stream');
      final request = http.Request('POST', streamUrl);
      request.headers.addAll({
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $_token',
        'Accept': 'text/event-stream',
      });
      request.body = jsonEncode(requestBody);

      final streamedResponse = await client.send(request);

      if (streamedResponse.statusCode == 200) {
        await for (final line in streamedResponse.stream
            .transform(utf8.decoder)
            .transform(const LineSplitter())) {
          if (!mounted) break;
          final trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          final jsonStr = trimmed.substring(6).trim();
          if (jsonStr.isEmpty) continue;

          try {
            final decoded = jsonDecode(jsonStr);
            if (decoded is! Map<String, dynamic>) continue;

            final type = decoded['type']?.toString();
            if (type == 'token') {
              final text = decoded['text']?.toString() ?? '';
              setState(() {
                assistantMessage.content += text;
              });
              _scrollToBottom();
            } else if (type == 'metadata') {
              final pages = decoded['source_pages'];
              if (pages is List) {
                setState(() {
                  assistantMessage.sourcePages = pages
                      .map((p) => int.tryParse(p.toString()) ?? 0)
                      .where((p) => p > 0)
                      .toList();
                });
              }
            } else if (type == 'done') {
              final pages = decoded['source_pages'];
              if (pages is List) {
                setState(() {
                  assistantMessage.sourcePages = pages
                      .map((p) => int.tryParse(p.toString()) ?? 0)
                      .where((p) => p > 0)
                      .toList();
                });
              }
            } else if (type == 'error') {
              final detail =
                  decoded['detail']?.toString() ?? 'Error from AI service';
              setState(() {
                if (assistantMessage.content.isEmpty) {
                  assistantMessage.content =
                      'Sorry, something went wrong:\n$detail';
                }
              });
            }
          } catch (_) {}
        }
      } else if (streamedResponse.statusCode == 429 ||
          streamedResponse.statusCode == 401 ||
          streamedResponse.statusCode == 403 ||
          streamedResponse.statusCode == 400) {
        // Direct rate limit or authorization error: do NOT send duplicate request to /ai/ask!
        String errorMessage = streamedResponse.statusCode == 429
            ? 'The AI service rate limit has been reached. Please wait a moment and try again.'
            : 'Request failed with status ${streamedResponse.statusCode}.';
        try {
          final body = await streamedResponse.stream.bytesToString();
          final dynamic decoded = jsonDecode(body);
          if (decoded is Map<String, dynamic> && decoded['detail'] != null) {
            errorMessage = decoded['detail'].toString();
          }
        } catch (_) {}
        if (!mounted) return;
        setState(() {
          assistantMessage.content = errorMessage;
        });
      } else {
        // Fallback to standard /ai/ask endpoint ONLY if SSE transport returned error (e.g. 404, 405, 502)
        final fallbackResponse = await http.post(
          Uri.parse('${ApiConstants.baseUrl}/ai/ask'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $_token',
          },
          body: jsonEncode(requestBody),
        );

        if (!mounted) return;

        if (fallbackResponse.statusCode == 200) {
          final dynamic decoded = jsonDecode(fallbackResponse.body);
          if (decoded is Map<String, dynamic>) {
            final answer =
                decoded['answer']?.toString() ?? 'No answer received.';
            final sourcePages = decoded['source_pages'];
            List<int> pagesList = [];
            if (sourcePages is List) {
              pagesList = sourcePages
                  .map((p) => int.tryParse(p.toString()) ?? 0)
                  .where((p) => p > 0)
                  .toList();
            }
            setState(() {
              assistantMessage.content = answer;
              assistantMessage.sourcePages = pagesList;
            });
          }
        } else {
          String errorMessage = 'Unable to get an answer.';
          try {
            final dynamic decoded = jsonDecode(fallbackResponse.body);
            if (decoded is Map<String, dynamic>) {
              errorMessage = decoded['detail']?.toString() ?? errorMessage;
            }
          } catch (_) {}
          setState(() {
            assistantMessage.content =
                'Sorry, something went wrong.\n$errorMessage';
          });
        }
      }
    } catch (e) {
      if (!mounted) return;
      if (assistantMessage.content.isEmpty) {
        setState(() {
          assistantMessage.content =
              'Could not connect to the AI Teacher. Please check your network and try again.';
        });
      }
    } finally {
      _currentClient = null;
      if (mounted) {
        setState(() {
          assistantMessage.isStreaming = false;
          _isLoading = false;
        });
        _scrollToBottom();
      }
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _startNewChat() {
    if (_isLoading) {
      _stopGeneration();
    }

    setState(() {
      _messages.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    const background = Color(0xFFF7F6FC);
    const primary = Color(0xFF6255D9);
    const textColor = Color(0xFF29283A);

    return Scaffold(
      backgroundColor: background,
      appBar: AppBar(
        backgroundColor: background,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(
            Icons.arrow_back_ios_new_rounded,
            size: 20,
            color: textColor,
          ),
          onPressed: () => Navigator.maybePop(context),
        ),
        titleSpacing: 0,
        title: Row(
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF8175F0), Color(0xFF5548CB)],
                ),
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(
                Icons.auto_awesome_rounded,
                color: Colors.white,
                size: 23,
              ),
            ),
            const SizedBox(width: 11),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'MindVault AI',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      color: textColor,
                    ),
                  ),
                  InkWell(
                    onTap: _userPdfs.length > 1 ? _showPdfSelector : null,
                    borderRadius: BorderRadius.circular(6),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Flexible(
                          child: Text(
                            _pdfId == null ? 'Personal AI Teacher' : _pdfTitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 11,
                              color: Color(0xFF77758C),
                            ),
                          ),
                        ),
                        if (_userPdfs.length > 1) ...[
                          const SizedBox(width: 3),
                          const Icon(
                            Icons.arrow_drop_down_rounded,
                            size: 16,
                            color: Color(0xFF77758C),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'New chat',
            onPressed: _startNewChat,
            icon: const Icon(Icons.add_comment_outlined, color: primary),
          ),
          const SizedBox(width: 5),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Container(
              margin: const EdgeInsets.fromLTRB(16, 5, 16, 10),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.8),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFE9E5FA)),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.lightbulb_outline_rounded,
                    color: primary,
                    size: 21,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _pdfId == null
                          ? 'Ask questions, learn concepts, and explore new ideas.'
                          : 'Grounded strictly in: $_pdfTitle',
                      style: const TextStyle(
                        fontSize: 12,
                        height: 1.5,
                        color: Color(0xFF69677D),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: _messages.isEmpty
                  ? _buildWelcome()
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                      itemCount: _messages.length,
                      itemBuilder: (context, index) {
                        return _buildMessageBubble(_messages[index]);
                      },
                    ),
            ),
            _buildInputArea(),
          ],
        ),
      ),
    );
  }

  Widget _buildWelcome() {
    const primary = Color(0xFF6255D9);
    final greetingTitle = _userName.isNotEmpty
        ? 'Hello $_userName!\nWhat would you like to learn today?'
        : 'What would you like to learn today?';

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 78,
              height: 78,
              decoration: BoxDecoration(
                color: const Color(0xFFEAE7FF),
                borderRadius: BorderRadius.circular(26),
              ),
              child: const Icon(
                Icons.auto_awesome_rounded,
                size: 39,
                color: primary,
              ),
            ),
            const SizedBox(height: 22),
            Text(
              greetingTitle,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: Color(0xFF29283A),
                height: 1.25,
              ),
            ),
            const SizedBox(height: 9),
            const Text(
              'Ask your AI teacher anything. Start with a question below.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                height: 1.6,
                color: Color(0xFF77758C),
              ),
            ),
            const SizedBox(height: 24),
            _suggestion(
              'Explain a concept in simple words',
              Icons.menu_book_rounded,
            ),
            const SizedBox(height: 10),
            _suggestion('Give me an example', Icons.lightbulb_outline_rounded),
            const SizedBox(height: 10),
            _suggestion(
              'Help me revise what I learned',
              Icons.psychology_alt_outlined,
            ),
          ],
        ),
      ),
    );
  }

  Widget _suggestion(String text, IconData icon) {
    return InkWell(
      onTap: _isLoading
          ? null
          : () {
              _messageController.text = text;
              _sendMessage();
            },
      borderRadius: BorderRadius.circular(15),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: const Color(0xFFE9E5F5)),
        ),
        child: Row(
          children: [
            Icon(icon, color: const Color(0xFF6255D9), size: 19),
            const SizedBox(width: 11),
            Expanded(
              child: Text(
                text,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF49475E),
                ),
              ),
            ),
            const Icon(
              Icons.arrow_forward_rounded,
              size: 17,
              color: Color(0xFF8B85BD),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageBubble(ChatMessage message) {
    final isUser = message.role == 'user';

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.85,
        ),
        margin: const EdgeInsets.only(bottom: 15),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: isUser ? const Color(0xFF6255D9) : Colors.white,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(isUser ? 18 : 5),
            bottomRight: Radius.circular(isUser ? 5 : 18),
          ),
          border: isUser ? null : Border.all(color: const Color(0xFFEAE7F5)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.025),
              blurRadius: 8,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: isUser
            ? Text(
                message.content,
                style: const TextStyle(
                  fontSize: 13.5,
                  height: 1.55,
                  color: Colors.white,
                  fontWeight: FontWeight.w500,
                ),
              )
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (message.content.isEmpty && message.isStreaming)
                    const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Color(0xFF6255D9),
                          ),
                        ),
                        SizedBox(width: 10),
                        Text(
                          'AI Teacher is thinking...',
                          style: TextStyle(
                            fontSize: 12.5,
                            color: Color(0xFF77758C),
                          ),
                        ),
                      ],
                    )
                  else
                    MarkdownBody(
                      data: message.content,
                      selectable: true,
                      styleSheet: MarkdownStyleSheet.fromTheme(
                        Theme.of(context),
                      ).copyWith(
                        p: const TextStyle(
                          fontSize: 13.5,
                          height: 1.55,
                          color: Color(0xFF39374B),
                        ),
                        h1: const TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF29283A),
                        ),
                        h2: const TextStyle(
                          fontSize: 15.5,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF29283A),
                        ),
                        h3: const TextStyle(
                          fontSize: 14.5,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF29283A),
                        ),
                        code: const TextStyle(
                          backgroundColor: Color(0xFFF1EFF9),
                          fontFamily: 'monospace',
                          fontSize: 12,
                          color: Color(0xFF6255D9),
                        ),
                        codeblockDecoration: BoxDecoration(
                          color: const Color(0xFFF6F5FB),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: const Color(0xFFE5E0F2)),
                        ),
                        blockquoteDecoration: BoxDecoration(
                          color: const Color(0xFFF8F7FD),
                          borderRadius: BorderRadius.circular(8),
                          border: const Border(
                            left: BorderSide(
                              color: Color(0xFF6255D9),
                              width: 3,
                            ),
                          ),
                        ),
                      ),
                    ),
                  if (message.isStreaming && message.content.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 6,
                            height: 6,
                            decoration: const BoxDecoration(
                              color: Color(0xFF6255D9),
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 6),
                          const Text(
                            'Streaming...',
                            style: TextStyle(
                              fontSize: 11,
                              fontStyle: FontStyle.italic,
                              color: Color(0xFF8B85BD),
                            ),
                          ),
                        ],
                      ),
                    ),
                  if (message.sourcePages.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: message.sourcePages.map((page) {
                        return Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFFEAE7FF),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(
                                Icons.description_outlined,
                                size: 12,
                                color: Color(0xFF6255D9),
                              ),
                              const SizedBox(width: 4),
                              Text(
                                'Page $page',
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                  color: Color(0xFF6255D9),
                                ),
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ],
              ),
      ),
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(
          top: BorderSide(
            color: const Color(0xFFEAE7F5).withValues(alpha: 0.8),
          ),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: _messageController,
              minLines: 1,
              maxLines: 5,
              textCapitalization: TextCapitalization.sentences,
              onSubmitted: (_) => _isLoading ? null : _sendMessage(),
              decoration: InputDecoration(
                hintText: _userName.isNotEmpty
                    ? 'Ask your question, $_userName...'
                    : 'Ask your AI teacher...',
                hintStyle: const TextStyle(
                  color: Color(0xFF9693A8),
                  fontSize: 13,
                ),
                filled: true,
                fillColor: const Color(0xFFF7F6FC),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 13,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(18),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),
          const SizedBox(width: 9),
          SizedBox(
            width: 48,
            height: 48,
            child: ElevatedButton(
              onPressed: _isLoading ? _stopGeneration : _sendMessage,
              style: ElevatedButton.styleFrom(
                backgroundColor: _isLoading
                    ? const Color(0xFFE53935)
                    : const Color(0xFF6255D9),
                foregroundColor: Colors.white,
                padding: EdgeInsets.zero,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
              child: Icon(
                _isLoading ? Icons.stop_rounded : Icons.arrow_upward_rounded,
                size: 23,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
