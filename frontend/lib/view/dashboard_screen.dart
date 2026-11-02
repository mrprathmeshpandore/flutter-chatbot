import 'package:flutter/material.dart';
import 'package:mind_ai/const/bottom_navigation.dart';
import 'package:mind_ai/model/progress_summary.dart';
import 'package:mind_ai/model/user_model.dart';
import 'package:mind_ai/repo/progress_repo.dart';
import 'package:mind_ai/repo/user_repo.dart';
import 'package:mind_ai/view/growth_screen.dart';
import 'package:mind_ai/view/learning_path_screen.dart';
import 'package:mind_ai/view/my_library_screen.dart';
import 'package:mind_ai/view/quiz_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  static const Color primary = Color(0xFF5965E8);
  static const Color textDark = Color(0xFF25252B);
  static const Color textMuted = Color(0xFF85859A);

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final UserRepo _userRepo = UserRepo();
  late Future<ProgressSummary> progressFuture;
  UserModel? _user;
  bool tokenMissing = false;
  bool initialized = false;

  // FIX: Store the login token for use by dashboard cards.
  String? token;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    if (initialized) return;
    initialized = true;

    final arguments = ModalRoute.of(context)?.settings.arguments;

    if (arguments is String && arguments.isNotEmpty) {
      token = arguments;
      progressFuture = ProgressRepo().getProgressSummary(token: arguments);
      _loadUserProfile();
    } else {
      tokenMissing = true;
    }
  }

  Future<void> _loadUserProfile() async {
    if (token == null || token!.isEmpty) return;

    // Load cached profile immediately
    final cached = await _userRepo.getCachedProfile();
    if (cached != null && mounted && _user == null) {
      setState(() => _user = cached);
    }

    try {
      final fresh = await _userRepo.getProfile(token: token!);
      if (mounted) {
        setState(() => _user = fresh);
      }
    } catch (_) {}
  }

  Widget _buildDashboardAvatar() {
    final avatarUrl = _user?.avatarFullUrl;
    final initials = _user?.initials ?? '';
    final hasPhoto = avatarUrl != null && avatarUrl.isNotEmpty;

    return CircleAvatar(
      radius: 21,
      backgroundColor: const Color(0xFFE0DEFF),
      backgroundImage: hasPhoto ? NetworkImage(avatarUrl) : null,
      child: !hasPhoto
          ? (initials.isNotEmpty
              ? Text(
                  initials,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: DashboardScreen.primary,
                  ),
                )
              : const Icon(
                  Icons.person_rounded,
                  color: DashboardScreen.primary,
                  size: 22,
                ))
          : null,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F7FF),
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
            padding: const EdgeInsets.fromLTRB(22, 18, 22, 28),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(11),
                      decoration: BoxDecoration(
                        color: DashboardScreen.primary,
                        borderRadius: BorderRadius.circular(15),
                        boxShadow: [
                          BoxShadow(
                            color: DashboardScreen.primary.withValues(
                              alpha: 0.22,
                            ),
                            blurRadius: 15,
                            offset: const Offset(0, 5),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.menu_book_rounded,
                        color: Colors.white,
                        size: 25,
                      ),
                    ),
                    const SizedBox(width: 11),
                    const Expanded(
                      child: Text(
                        'MindVault AI',
                        style: TextStyle(
                          fontSize: 19,
                          fontWeight: FontWeight.w800,
                          color: DashboardScreen.textDark,
                          letterSpacing: -0.6,
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Notifications coming soon'),
                          ),
                        );
                      },
                      icon: const Icon(
                        Icons.notifications_none_rounded,
                        color: DashboardScreen.textDark,
                      ),
                    ),
                    GestureDetector(
                      onTap: () async {
                        if (token == null || token!.isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Login token missing. Please log in again.'),
                            ),
                          );
                          return;
                        }

                        final result = await Navigator.pushNamed(
                          context,
                          '/profile',
                          arguments: {
                            'token': token,
                            'user': _user,
                          },
                        );

                        if (result is UserModel && mounted) {
                          setState(() => _user = result);
                        } else if (mounted) {
                          _loadUserProfile();
                        }
                      },
                      child: _buildDashboardAvatar(),
                    ),
                  ],
                ),

                const SizedBox(height: 32),

                // Welcome
                const Text(
                  'YOUR PERSONAL AI LEARNING SPACE',
                  style: TextStyle(
                    color: DashboardScreen.primary,
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.3,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  _user != null && _user!.displayName.isNotEmpty
                      ? 'Ready to learn something\nnew today, ${_user!.displayName}?'
                      : 'Ready to learn something\nnew today?',
                  style: const TextStyle(
                    color: DashboardScreen.textDark,
                    fontSize: 29,
                    height: 1.2,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -1,
                  ),
                ),
                const SizedBox(height: 10),
                const Text(
                  'Your notes. Your pace. Your potential.',
                  style: TextStyle(
                    fontSize: 13,
                    color: DashboardScreen.textMuted,
                    height: 1.5,
                  ),
                ),

                const SizedBox(height: 24),

                // AI Teacher card
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(22),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFF626EEB), Color(0xFF8B83F5)],
                    ),
                    borderRadius: BorderRadius.circular(25),
                    boxShadow: [
                      BoxShadow(
                        color: DashboardScreen.primary.withValues(alpha: 0.19),
                        blurRadius: 22,
                        offset: const Offset(0, 9),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(11),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.17),
                          borderRadius: BorderRadius.circular(15),
                        ),
                        child: const Icon(
                          Icons.auto_awesome_rounded,
                          color: Colors.white,
                          size: 27,
                        ),
                      ),
                      const SizedBox(height: 17),
                      const Text(
                        'Meet your AI Teacher',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.5,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Ask questions, understand complex topics, '
                        'and learn directly from your PDFs.',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.88),
                          fontSize: 12,
                          height: 1.6,
                        ),
                      ),
                      const SizedBox(height: 20),
                      ElevatedButton.icon(
                        onPressed: () {
                          if (token == null || token!.isEmpty) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text(
                                  'Login token missing. Please log in again.',
                                ),
                              ),
                            );
                            return;
                          }

                          Navigator.pushNamed(
                            context,
                            '/chatbot',
                            arguments: token,
                          );
                        },
                        icon: const Icon(Icons.arrow_forward_rounded, size: 18),
                        label: const Text('Start learning'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.white,
                          foregroundColor: DashboardScreen.primary,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 18,
                            vertical: 14,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(13),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 30),

                const Text(
                  'Your learning space',
                  style: TextStyle(
                    color: DashboardScreen.textDark,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.5,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Everything you need, in one place.',
                  style: TextStyle(
                    color: DashboardScreen.textMuted,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 18),

                GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisSpacing: 13,
                  mainAxisSpacing: 13,
                  childAspectRatio: 0.98,
                  children: [
                    _FeatureCard(
                      icon: Icons.folder_open_rounded,
                      title: 'My Library',
                      subtitle: 'Your saved PDFs',
                      color: const Color(0xFF5965E8),
                      background: const Color(0xFFECEBFF),
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const MyLibraryScreen(),
                            settings: RouteSettings(arguments: token),
                          ),
                        );
                      },
                    ),
                    _FeatureCard(
                      icon: Icons.route_rounded,
                      title: 'Learning Path',
                      subtitle: 'Your study plan',
                      color: const Color(0xFF159C86),
                      background: const Color(0xFFE1F7F0),
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const LearningPathScreen(),
                            settings: RouteSettings(arguments: token),
                          ),
                        );
                      },
                    ),
                    _FeatureCard(
                      icon: Icons.psychology_alt_rounded,
                      title: 'AI Teacher',
                      subtitle: 'Ask and understand',
                      color: const Color(0xFF9860D8),
                      background: const Color(0xFFF1E6FF),
                      onTap: () {
                        if (token == null || token!.isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'Login token missing. Please log in again.',
                              ),
                            ),
                          );
                          return;
                        }

                        Navigator.pushNamed(
                          context,
                          '/chatbot',
                          arguments: token,
                        );
                      },
                    ),
                    _FeatureCard(
                      icon: Icons.quiz_rounded,
                      title: 'Quiz & Practice',
                      subtitle: 'Test your knowledge',
                      color: const Color(0xFFE08A43),
                      background: const Color(0xFFFFF0E1),
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const QuizScreen(),
                            settings: RouteSettings(arguments: token),
                          ),
                        );
                      },
                    ),
                  ],
                ),

                const SizedBox(height: 28),

                // Progress section
                Row(
                  children: [
                    const Expanded(
                      child: Text(
                        'Your progress',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                          color: DashboardScreen.textDark,
                          letterSpacing: -0.5,
                        ),
                      ),
                    ),
                    Icon(
                      Icons.trending_up_rounded,
                      color: Colors.green.shade700,
                      size: 23,
                    ),
                  ],
                ),
                const SizedBox(height: 15),

                if (tokenMissing)
                  _messageCard(
                    'Login token missing. Please log in again.',
                    Icons.lock_outline_rounded,
                  )
                else
                  FutureBuilder<ProgressSummary>(
                    future: progressFuture,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState == ConnectionState.waiting) {
                        return _messageCard(
                          'Loading your progress...',
                          Icons.hourglass_top_rounded,
                          loading: true,
                        );
                      }

                      if (snapshot.hasError) {
                        return Column(
                          children: [
                            _messageCard(
                              'Could not load progress.\n${snapshot.error}',
                              Icons.error_outline_rounded,
                            ),
                            const SizedBox(height: 8),
                            OutlinedButton.icon(
                              onPressed: () {
                                if (token == null || token!.isEmpty) {
                                  return;
                                }

                                setState(() {
                                  progressFuture = ProgressRepo()
                                      .getProgressSummary(token: token!);
                                });
                              },
                              icon: const Icon(Icons.refresh_rounded),
                              label: const Text('Retry'),
                            ),
                          ],
                        );
                      }

                      if (!snapshot.hasData) {
                        return _messageCard(
                          'No progress data available.',
                          Icons.info_outline_rounded,
                        );
                      }

                      final progress = snapshot.data!;

                      return Column(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(19),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.88),
                              borderRadius: BorderRadius.circular(22),
                              border: Border.all(
                                color: const Color(0xFFEAE8F5),
                              ),
                            ),
                            child: Column(
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: _StatItem(
                                        value: '${progress.totalPdfs}',
                                        label: 'PDFs uploaded',
                                        icon: Icons.picture_as_pdf_rounded,
                                        color: DashboardScreen.primary,
                                      ),
                                    ),
                                    Container(
                                      width: 1,
                                      height: 53,
                                      color: const Color(0xFFEAE8F5),
                                    ),
                                    Expanded(
                                      child: _StatItem(
                                        value: '${progress.totalQuizzesTaken}',
                                        label: 'Quizzes taken',
                                        icon: Icons.task_alt_rounded,
                                        color: const Color(0xFF159C86),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 20),
                                const Divider(color: Color(0xFFEAE8F5)),
                                const SizedBox(height: 17),
                                Row(
                                  children: [
                                    Expanded(
                                      child: _StatItem(
                                        value: '${progress.averageQuizScore}%',
                                        label: 'Average quiz score',
                                        icon: Icons.insights_rounded,
                                        color: const Color(0xFFE08A43),
                                      ),
                                    ),
                                    Container(
                                      width: 1,
                                      height: 53,
                                      color: const Color(0xFFEAE8F5),
                                    ),
                                    Expanded(
                                      child: _StatItem(
                                        value: '${progress.learningPathsCount}',
                                        label: 'Learning paths',
                                        icon: Icons.route_rounded,
                                        color: const Color(0xFF9860D8),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),

                          const SizedBox(height: 24),

                          if (progress.recentActivity.isNotEmpty) ...[
                            const Align(
                              alignment: Alignment.centerLeft,
                              child: Text(
                                'Recent activity',
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w800,
                                  color: DashboardScreen.textDark,
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            Container(
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.90),
                                borderRadius: BorderRadius.circular(20),
                                border: Border.all(
                                  color: const Color(0xFFEAE8F5),
                                ),
                              ),
                              child: Column(
                                children: progress.recentActivity
                                    .take(5)
                                    .map(
                                      (activity) => ListTile(
                                        contentPadding:
                                            const EdgeInsets.symmetric(
                                              horizontal: 2,
                                              vertical: 3,
                                            ),
                                        leading: const CircleAvatar(
                                          backgroundColor: Color(0xFFECEBFF),
                                          child: Icon(
                                            Icons.history_rounded,
                                            color: DashboardScreen.primary,
                                          ),
                                        ),
                                        title: Text(
                                          activity.subject,
                                          style: const TextStyle(
                                            fontSize: 13,
                                            fontWeight: FontWeight.w700,
                                            color: DashboardScreen.textDark,
                                          ),
                                        ),
                                        subtitle: Text(
                                          '${activity.activityType} • '
                                          '${_formatDate(activity.createdAt)}',
                                          style: const TextStyle(
                                            fontSize: 11,
                                            color: DashboardScreen.textMuted,
                                          ),
                                        ),
                                        trailing: activity.score == null
                                            ? null
                                            : Text(
                                                '${activity.score}',
                                                style: const TextStyle(
                                                  fontWeight: FontWeight.w800,
                                                  color:
                                                      DashboardScreen.primary,
                                                ),
                                              ),
                                      ),
                                    )
                                    .toList(),
                              ),
                            ),
                          ],
                        ],
                      );
                    },
                  ),

                const SizedBox(height: 25),

                const Center(
                  child: Text(
                    'Small steps. Big progress. ✨',
                    style: TextStyle(
                      fontSize: 11,
                      color: DashboardScreen.textMuted,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      bottomNavigationBar: BottomNavigation(
        currentIndex: 0,
        onTap: (index) {
          switch (index) {
            case 0:
              break;
            case 1:
              if (token == null || token!.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Login token missing. Please log in again.'),
                  ),
                );
                return;
              }

              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const MyLibraryScreen(),
                  settings: RouteSettings(arguments: token),
                ),
              );
              break;
            case 2:
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const LearningPathScreen(),
                  settings: RouteSettings(arguments: token),
                ),
              );
              break;
            case 3:
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const GrowthScreen(),
                  settings: RouteSettings(arguments: token),
                ),
              );
              break;
          }
        },
      ),
    );
  }

  static Widget _messageCard(
    String message,
    IconData icon, {
    bool loading = false,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.90),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFEAE8F5)),
      ),
      child: Column(
        children: [
          if (loading)
            const CircularProgressIndicator()
          else
            Icon(icon, color: DashboardScreen.primary, size: 28),
          const SizedBox(height: 12),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 12,
              height: 1.5,
              color: DashboardScreen.textMuted,
            ),
          ),
        ],
      ),
    );
  }

  static String _formatDate(String value) {
    final date = DateTime.tryParse(value);
    if (date == null) return value;

    final localDate = date.toLocal();

    return '${localDate.day.toString().padLeft(2, '0')}/'
        '${localDate.month.toString().padLeft(2, '0')}/'
        '${localDate.year}';
  }


}

class _FeatureCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final Color background;
  final VoidCallback onTap;

  const _FeatureCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
    required this.background,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.91),
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Container(
          padding: const EdgeInsets.all(17),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: const Color(0xFFEAE8F5)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: background,
                  borderRadius: BorderRadius.circular(15),
                ),
                child: Icon(icon, color: color, size: 25),
              ),
              const Spacer(),
              Text(
                title,
                style: const TextStyle(
                  color: Color(0xFF25252B),
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                subtitle,
                style: const TextStyle(color: Color(0xFF85859A), fontSize: 10),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  final String value;
  final String label;
  final IconData icon;
  final Color color;

  const _StatItem({
    required this.value,
    required this.label,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, color: color, size: 23),
        const SizedBox(height: 9),
        Text(
          value,
          style: const TextStyle(
            fontSize: 25,
            fontWeight: FontWeight.w800,
            color: Color(0xFF25252B),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 10, color: Color(0xFF85859A)),
        ),
      ],
    );
  }
}
