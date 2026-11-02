import 'package:flutter/material.dart';
import 'package:mind_ai/const/app_colors.dart';
import 'package:mind_ai/const/custom_background.dart';
import 'package:mind_ai/const/custom_button_widget.dart';
import 'package:mind_ai/repo/auth_repo.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final nameController = TextEditingController();
  final emailController = TextEditingController();
  final passwordController = TextEditingController();

  bool hidePassword = true;
  bool isLoading = false;

  @override
  void dispose() {
    nameController.dispose();
    emailController.dispose();
    passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: CustomBackground(
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 12, 24, 20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Back button and logo
                Row(
                  children: [
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.arrow_back_ios_new, size: 18),
                    ),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.all(7),
                      decoration: BoxDecoration(
                        color: AppColors.primaryColor,
                        borderRadius: BorderRadius.circular(10),
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.primaryColor.withValues(
                              alpha: 0.20,
                            ),
                            blurRadius: 14,
                            offset: const Offset(0, 5),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.menu_book_outlined,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Text('MindVault AI', style: TextStyle(fontSize: 15)),
                  ],
                ),

                const SizedBox(height: 46),

                const Text(
                  'Make room for growth.',
                  style: TextStyle(
                    fontSize: 30,
                    height: 1.2,
                    fontWeight: FontWeight.w700,
                    letterSpacing: -1,
                    color: Color(0xFF25252B),
                  ),
                ),

                const SizedBox(height: 8),

                const Text(
                  'Create your free account. Your next “aha” moment \nstarts here.',
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.5,
                    color: Color(0xFF777789),
                  ),
                ),

                const SizedBox(height: 32),

                const Text('Full name', style: TextStyle(fontSize: 12)),
                const SizedBox(height: 9),

                TextField(
                  controller: nameController,
                  decoration: inputDecoration(
                    'Enter your name',
                    Icons.person_outline,
                  ),
                ),

                const SizedBox(height: 20),

                const Text('Student email', style: TextStyle(fontSize: 12)),
                const SizedBox(height: 9),

                TextField(
                  controller: emailController,
                  keyboardType: TextInputType.emailAddress,
                  decoration: inputDecoration(
                    'Enter your email',
                    Icons.mail_outline,
                  ),
                ),

                const SizedBox(height: 20),

                const Text('Password', style: TextStyle(fontSize: 12)),
                const SizedBox(height: 9),

                TextField(
                  controller: passwordController,
                  obscureText: hidePassword,
                  decoration: InputDecoration(
                    hintText: 'Create a password',
                    hintStyle: const TextStyle(fontSize: 14),
                    prefixIcon: const Icon(Icons.lock_outline, size: 20),
                    suffixIcon: IconButton(
                      onPressed: () {
                        setState(() {
                          hidePassword = !hidePassword;
                        });
                      },
                      icon: Icon(
                        hidePassword
                            ? Icons.visibility_off_outlined
                            : Icons.visibility_outlined,
                        size: 20,
                      ),
                    ),
                    filled: true,
                    fillColor: Colors.white,
                    contentPadding: const EdgeInsets.symmetric(vertical: 14),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(13),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),

                const SizedBox(height: 12),

                const Text(
                  'At least 8 characters. Make it uniquely yours.',
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.5,
                    color: Color(0xFF818092),
                  ),
                ),

                const SizedBox(height: 14),

                SizedBox(
                  width: double.infinity,
                  child: CustomButton(
                    title: isLoading ? 'Creating account...' : 'Create account',
                    onPressed: () async {
                      if (isLoading) return;

                      final name = nameController.text.trim();
                      final email = emailController.text.trim();
                      final password = passwordController.text;

                      if (name.isEmpty || email.isEmpty || password.isEmpty) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Please fill all fields'),
                          ),
                        );
                        return;
                      }

                      if (!email.contains('@')) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Please enter a valid email'),
                          ),
                        );
                        return;
                      }

                      if (password.length < 8) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              'Password must be at least 8 characters',
                            ),
                          ),
                        );
                        return;
                      }

                      final messenger = ScaffoldMessenger.of(context);
                      final navigator = Navigator.of(context);

                      setState(() {
                        isLoading = true;
                      });

                      try {
                        await AuthRepo().register(
                          fullName: name,
                          email: email,
                          password: password,
                        );

                        messenger.showSnackBar(
                          const SnackBar(
                            content: Text(
                              'Account created successfully! Please sign in.',
                            ),
                          ),
                        );

                        navigator.pushReplacementNamed('/login');
                      } catch (e) {
                        messenger.showSnackBar(
                          SnackBar(
                            content: Text(
                              e.toString().replaceFirst('Exception: ', ''),
                            ),
                          ),
                        );
                      } finally {
                        if (mounted) {
                          setState(() {
                            isLoading = false;
                          });
                        }
                      }
                    },
                  ),
                ),

                const SizedBox(height: 14),

                const Center(
                  child: Text(
                    'or continue with',
                    style: TextStyle(fontSize: 13, color: Color(0xFF818092)),
                  ),
                ),

                const SizedBox(height: 12),

                Row(
                  children: [
                    Expanded(
                      child: socialButton(Icons.g_mobiledata_rounded, 'Google'),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: socialButton(Icons.school_outlined, 'University'),
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                const Center(
                  child: Text(
                    'By joining, you agree to our Terms of Service '
                    'and Privacy Policy.\nYour PDFs stay private.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 11,
                      height: 1.5,
                      color: Color(0xFF818092),
                    ),
                  ),
                ),

                const SizedBox(height: 12),

                Center(
                  child: Wrap(
                    alignment: WrapAlignment.center,
                    children: [
                      const Text(
                        'Already a member? ',
                        style: TextStyle(fontSize: 14),
                      ),
                      GestureDetector(
                        onTap: () {
                          Navigator.pushNamed(context, '/login');
                        },
                        child: const Text(
                          'Sign in',
                          style: TextStyle(
                            fontSize: 14,
                            color: Color(0xFF3849E8),
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
        ),
      ),
    );
  }

  InputDecoration inputDecoration(String hint, IconData icon) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(fontSize: 13, color: Color(0xFF9290A0)),
      prefixIcon: Icon(icon, size: 19, color: const Color(0xFF777789)),
      filled: true,
      fillColor: Colors.white.withValues(alpha: 0.90),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 17),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(15),
        borderSide: const BorderSide(color: Color(0xFFE6E3F0)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(15),
        borderSide: BorderSide(color: AppColors.primaryColor, width: 1.5),
      ),
    );
  }

  Widget socialButton(IconData icon, String title) {
    return SizedBox(
      height: 42,
      child: ElevatedButton.icon(
        onPressed: () {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('$title sign-in will be added later')),
          );
        },
        icon: Icon(icon, size: 22),
        label: Text(title, style: const TextStyle(fontSize: 13)),
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: AppColors.blackColor,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }
}
