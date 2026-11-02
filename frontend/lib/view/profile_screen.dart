import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:mind_ai/model/user_model.dart';
import 'package:mind_ai/repo/user_repo.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  static const Color primary = Color(0xFF5965E8);
  static const Color primaryDark = Color(0xFF4552D4);
  static const Color textDark = Color(0xFF25252B);
  static const Color textMuted = Color(0xFF85859A);
  static const Color background = Color(0xFFF8F7FF);
  static const Color cardBorder = Color(0xFFECEBFF);

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final UserRepo _userRepo = UserRepo();
  final _formKey = GlobalKey<FormState>();

  late TextEditingController _fullNameController;
  late TextEditingController _emailController;
  late TextEditingController _phoneController;

  String _token = '';
  UserModel? _user;
  bool _isLoading = true;
  bool _isSaving = false;
  bool _isUploadingPhoto = false;
  bool _argsLoaded = false;

  @override
  void initState() {
    super.initState();
    _fullNameController = TextEditingController();
    _emailController = TextEditingController();
    _phoneController = TextEditingController();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_argsLoaded) return;
    _argsLoaded = true;

    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is String) {
      _token = args;
    } else if (args is Map) {
      _token = args['token']?.toString() ?? '';
      if (args['user'] is UserModel) {
        _user = args['user'] as UserModel;
        _populateFields(_user!);
      }
    }

    _loadProfile();
  }

  @override
  void dispose() {
    _fullNameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  void _populateFields(UserModel user) {
    _fullNameController.text = user.fullName ?? '';
    _emailController.text = user.email;
    _phoneController.text = user.phoneNumber ?? '';
  }

  Future<void> _loadProfile() async {
    if (_token.isEmpty) {
      setState(() => _isLoading = false);
      return;
    }

    try {
      // First try to load cached profile for instantaneous UI rendering
      final cached = await _userRepo.getCachedProfile();
      if (cached != null && mounted && _user == null) {
        setState(() {
          _user = cached;
          _populateFields(cached);
        });
      }

      // Refresh from backend server
      final freshUser = await _userRepo.getProfile(token: _token);
      if (mounted) {
        setState(() {
          _user = freshUser;
          _populateFields(freshUser);
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        if (_user == null) {
          _showSnackBar('Could not load profile: $e', isError: true);
        }
      }
    }
  }

  Future<void> _pickAndUploadPhoto() async {
    if (_token.isEmpty) {
      _showSnackBar('Login token is missing.', isError: true);
      return;
    }

    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.image,
        allowMultiple: false,
        withData: true,
      );

      if (result == null || result.files.isEmpty) return;

      final file = result.files.first;
      List<int>? bytes = file.bytes;

      if (bytes == null && file.path != null) {
        final ioFile = File(file.path!);
        bytes = await ioFile.readAsBytes();
      }

      if (bytes == null || bytes.isEmpty) {
        _showSnackBar('Could not read image file.', isError: true);
        return;
      }

      if (bytes.length > 5 * 1024 * 1024) {
        _showSnackBar('Image size exceeds maximum limit of 5 MB.', isError: true);
        return;
      }

      String filename = file.name;
      if (filename.isEmpty && file.path != null) {
        filename = file.path!.split(Platform.pathSeparator).last;
      }
      if (filename.isEmpty) {
        filename = 'profile_photo.jpg';
      }

      setState(() => _isUploadingPhoto = true);

      final updatedUser = await _userRepo.uploadAvatar(
        token: _token,
        bytes: bytes,
        filename: filename,
      );

      if (mounted) {
        setState(() {
          _user = updatedUser;
          _isUploadingPhoto = false;
        });
        _showSnackBar('Profile photo updated successfully!');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isUploadingPhoto = false);
        _showSnackBar(e.toString().replaceAll('Exception: ', ''), isError: true);
      }
    }
  }

  Future<void> _confirmRemovePhoto() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text(
          'Remove Profile Photo',
          style: TextStyle(fontWeight: FontWeight.w700, fontSize: 18),
        ),
        content: const Text(
          'Are you sure you want to remove your profile photo? Your avatar will revert to your name initials.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel', style: TextStyle(color: ProfileScreen.textMuted)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFE53935),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      setState(() => _isUploadingPhoto = true);
      final updatedUser = await _userRepo.deleteAvatar(token: _token);
      if (mounted) {
        setState(() {
          _user = updatedUser;
          _isUploadingPhoto = false;
        });
        _showSnackBar('Profile photo removed.');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isUploadingPhoto = false);
        _showSnackBar(e.toString().replaceAll('Exception: ', ''), isError: true);
      }
    }
  }

  Future<void> _saveProfileChanges() async {
    if (!_formKey.currentState!.validate()) return;
    if (_token.isEmpty) {
      _showSnackBar('Login token is missing.', isError: true);
      return;
    }

    setState(() => _isSaving = true);

    try {
      final updatedUser = await _userRepo.updateProfile(
        token: _token,
        fullName: _fullNameController.text.trim(),
        email: _emailController.text.trim(),
        phoneNumber: _phoneController.text.trim(),
      );

      if (mounted) {
        setState(() {
          _user = updatedUser;
          _populateFields(updatedUser);
          _isSaving = false;
        });
        _showSnackBar('Profile information updated successfully!');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isSaving = false);
        _showSnackBar(e.toString().replaceAll('Exception: ', ''), isError: true);
      }
    }
  }

  Future<void> _confirmLogout() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text(
          'Log Out',
          style: TextStyle(fontWeight: FontWeight.w700, fontSize: 18),
        ),
        content: const Text('Are you sure you want to log out of MindVault AI?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel', style: TextStyle(color: ProfileScreen.textMuted)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFE53935),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Log Out'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    await _userRepo.clearCache();
    if (!mounted) return;
    Navigator.pushNamedAndRemoveUntil(context, '/login', (route) => false);
  }

  void _showSnackBar(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          message,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        backgroundColor: isError ? const Color(0xFFD32F2F) : const Color(0xFF2E7D32),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        margin: const EdgeInsets.all(16),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ProfileScreen.background,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFFF1EFFF), Color(0xFFFBF9FF), Color(0xFFEFF8FF)],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              _buildTopBar(),
              Expanded(
                child: _isLoading
                    ? const Center(
                        child: CircularProgressIndicator(
                          color: ProfileScreen.primary,
                        ),
                      )
                    : SingleChildScrollView(
                        padding: const EdgeInsets.fromLTRB(22, 10, 22, 32),
                        child: Form(
                          key: _formKey,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.center,
                            children: [
                              _buildAvatarSection(),
                              const SizedBox(height: 28),
                              _buildFormCard(),
                              const SizedBox(height: 20),
                              _buildSaveButton(),
                              const SizedBox(height: 20),
                              _buildAccountInfoCard(),
                              const SizedBox(height: 20),
                              _buildLogoutButton(),
                            ],
                          ),
                        ),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      child: Row(
        children: [
          IconButton(
            onPressed: () => Navigator.maybePop(context, _user),
            icon: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: ProfileScreen.cardBorder),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: const Icon(
                Icons.arrow_back_ios_new_rounded,
                size: 18,
                color: ProfileScreen.textDark,
              ),
            ),
          ),
          const SizedBox(width: 8),
          const Text(
            'My Profile',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: ProfileScreen.textDark,
              letterSpacing: -0.5,
            ),
          ),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: const Color(0xFFEBE8FF),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: Color(0xFF388E3C),
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
                const Text(
                  'Active',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: ProfileScreen.primary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAvatarSection() {
    final avatarUrl = _user?.avatarFullUrl;
    final initials = _user?.initials ?? 'U';
    final hasPhoto = avatarUrl != null && avatarUrl.isNotEmpty;

    return Column(
      children: [
        Stack(
          alignment: Alignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  colors: [ProfileScreen.primary, Color(0xFF8B96FF)],
                ),
                boxShadow: [
                  BoxShadow(
                    color: ProfileScreen.primary.withValues(alpha: 0.28),
                    blurRadius: 20,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: CircleAvatar(
                radius: 54,
                backgroundColor: const Color(0xFFE8E5FF),
                backgroundImage: hasPhoto ? NetworkImage(avatarUrl) : null,
                child: !hasPhoto
                    ? Text(
                        initials,
                        style: const TextStyle(
                          fontSize: 34,
                          fontWeight: FontWeight.w800,
                          color: ProfileScreen.primary,
                        ),
                      )
                    : null,
              ),
            ),
            if (_isUploadingPhoto)
              Container(
                width: 116,
                height: 116,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.black.withValues(alpha: 0.45),
                ),
                child: const Center(
                  child: CircularProgressIndicator(
                    color: Colors.white,
                    strokeWidth: 3,
                  ),
                ),
              ),
            Positioned(
              bottom: 0,
              right: 0,
              child: GestureDetector(
                onTap: _isUploadingPhoto ? null : _pickAndUploadPhoto,
                child: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: ProfileScreen.primary,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 3),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.15),
                        blurRadius: 10,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.camera_alt_rounded,
                    color: Colors.white,
                    size: 18,
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 14),
        Text(
          _user?.displayName ?? 'Student',
          style: const TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w800,
            color: ProfileScreen.textDark,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          _user?.email ?? '',
          style: const TextStyle(
            fontSize: 13,
            color: ProfileScreen.textMuted,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 10,
          children: [
            OutlinedButton.icon(
              onPressed: _isUploadingPhoto ? null : _pickAndUploadPhoto,
              icon: const Icon(Icons.photo_library_rounded, size: 16),
              label: Text(hasPhoto ? 'Change Photo' : 'Upload Photo'),
              style: OutlinedButton.styleFrom(
                foregroundColor: ProfileScreen.primary,
                side: const BorderSide(color: Color(0xFFC7C2FA)),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              ),
            ),
            if (hasPhoto)
              OutlinedButton.icon(
                onPressed: _isUploadingPhoto ? null : _confirmRemovePhoto,
                icon: const Icon(Icons.delete_outline_rounded, size: 16),
                label: const Text('Remove'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFFE53935),
                  side: const BorderSide(color: Color(0xFFFFCDD2)),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                ),
              ),
          ],
        ),
      ],
    );
  }

  Widget _buildFormCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: ProfileScreen.cardBorder),
        boxShadow: [
          BoxShadow(
            color: ProfileScreen.primary.withValues(alpha: 0.06),
            blurRadius: 18,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFECEBFF),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(
                  Icons.person_outline_rounded,
                  color: ProfileScreen.primary,
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              const Text(
                'Personal Information',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: ProfileScreen.textDark,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Full Name Field
          _buildInputLabel('Full Name'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _fullNameController,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
            decoration: _inputDecoration(
              hint: 'Enter your full name',
              prefixIcon: Icons.badge_outlined,
            ),
            validator: (value) {
              if (value == null || value.trim().isEmpty) {
                return 'Full name cannot be empty';
              }
              if (value.trim().length < 2) {
                return 'Full name must be at least 2 characters';
              }
              return null;
            },
          ),
          const SizedBox(height: 18),

          // Email Field
          _buildInputLabel('Email Address'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _emailController,
            keyboardType: TextInputType.emailAddress,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
            decoration: _inputDecoration(
              hint: 'Enter your email address',
              prefixIcon: Icons.email_outlined,
            ),
            validator: (value) {
              if (value == null || value.trim().isEmpty) {
                return 'Email address cannot be empty';
              }
              final emailRegex = RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$');
              if (!emailRegex.hasMatch(value.trim())) {
                return 'Enter a valid email address';
              }
              return null;
            },
          ),
          const SizedBox(height: 18),

          // Phone Number Field
          _buildInputLabel('Phone Number (Optional)'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _phoneController,
            keyboardType: TextInputType.phone,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
            decoration: _inputDecoration(
              hint: '+1 234 567 8900',
              prefixIcon: Icons.phone_outlined,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputLabel(String label) {
    return Text(
      label,
      style: const TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w700,
        color: ProfileScreen.textMuted,
        letterSpacing: 0.3,
      ),
    );
  }

  InputDecoration _inputDecoration({
    required String hint,
    required IconData prefixIcon,
  }) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(
        fontSize: 13,
        color: Color(0xFFB0ADC0),
        fontWeight: FontWeight.w400,
      ),
      prefixIcon: Icon(prefixIcon, color: ProfileScreen.primary, size: 20),
      filled: true,
      fillColor: const Color(0xFFF9F8FE),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xFFE2E0F5)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xFFE2E0F5)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: ProfileScreen.primary, width: 1.8),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xFFD32F2F)),
      ),
    );
  }

  Widget _buildSaveButton() {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton(
        onPressed: _isSaving ? null : _saveProfileChanges,
        style: ElevatedButton.styleFrom(
          backgroundColor: ProfileScreen.primary,
          foregroundColor: Colors.white,
          elevation: 4,
          shadowColor: ProfileScreen.primary.withValues(alpha: 0.4),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
        child: _isSaving
            ? const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(
                  color: Colors.white,
                  strokeWidth: 2.5,
                ),
              )
            : const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.check_circle_outline_rounded, size: 20),
                  SizedBox(width: 8),
                  Text(
                    'Save Changes',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.2,
                    ),
                  ),
                ],
              ),
      ),
    );
  }

  Widget _buildAccountInfoCard() {
    String joinedDate = 'Recently';
    if (_user?.createdAt != null) {
      try {
        final parsed = DateTime.parse(_user!.createdAt!);
        joinedDate = '${parsed.day}/${parsed.month}/${parsed.year}';
      } catch (_) {}
    }

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.8),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: ProfileScreen.cardBorder),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _buildInfoItem(
            icon: Icons.calendar_today_rounded,
            title: 'Member Since',
            value: joinedDate,
          ),
          Container(
            height: 36,
            width: 1,
            color: const Color(0xFFE2E0F5),
          ),
          _buildInfoItem(
            icon: Icons.verified_user_outlined,
            title: 'Account Status',
            value: _user?.isActive == true ? 'Active' : 'Pending',
          ),
        ],
      ),
    );
  }

  Widget _buildInfoItem({
    required IconData icon,
    required String title,
    required String value,
  }) {
    return Column(
      children: [
        Icon(icon, size: 20, color: ProfileScreen.primary),
        const SizedBox(height: 6),
        Text(
          title,
          style: const TextStyle(
            fontSize: 11,
            color: ProfileScreen.textMuted,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w700,
            color: ProfileScreen.textDark,
          ),
        ),
      ],
    );
  }

  Widget _buildLogoutButton() {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: _confirmLogout,
        icon: const Icon(Icons.logout_rounded, color: Color(0xFFE53935), size: 19),
        label: const Text(
          'Log Out',
          style: TextStyle(
            color: Color(0xFFE53935),
            fontWeight: FontWeight.w700,
            fontSize: 15,
          ),
        ),
        style: OutlinedButton.styleFrom(
          side: const BorderSide(color: Color(0xFFFFCDD2), width: 1.2),
          backgroundColor: Colors.white.withValues(alpha: 0.6),
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      ),
    );
  }
}
