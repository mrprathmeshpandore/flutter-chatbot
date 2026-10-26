import 'package:flutter/material.dart';
import 'package:mind_ai/const/app_colors.dart';
import 'package:mind_ai/const/app_strings.dart';
import 'package:mind_ai/const/custom_background.dart';
// import 'package:mind_ai/view/login_screen.dart';
// import 'package:mind_ai/view/register_screen.dart';

class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: CustomBackground(
        child: SafeArea(
          child: SingleChildScrollView(
            child: Padding(
              padding:  EdgeInsets.fromLTRB(24, 24, 24, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                 Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                     Row(
                    children: [
                      Container(
                        padding: EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AppColors.primaryColor,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(
                          Icons.menu_book_outlined,
                          color: Colors.white,
                          size: 24,
                        ),
                      ),
                      SizedBox(width: 10),
                      Text(
                        AppStrings.appName,
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                          color: Color(0xFF202124),
                        ),
                      ),
                    ],
                  ),
                  SizedBox(height: 45),
                  Center(
                    child: SizedBox(
                      height: 190,
                      width: 270,
                      child: Stack(
                        clipBehavior: Clip.none,
                        children: [
                          Positioned(
                            left: 12,
                            right: 12,
                            top: 15,
                            bottom: 5,
                            child: Transform.rotate(
                              angle: -0.10,
                              child: Container(
                                padding: EdgeInsets.all(20),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(24),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.indigo.withValues(
                                        alpha: 0.08,
                                      ),
                                      blurRadius: 24,
                                      offset: Offset(0, 10),
                                    ),
                                  ],
                                ),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Icon(
                                          Icons.description_outlined,
                                          size: 17,
                                          color: Color(0xFF5965F0),
                                        ),
                                        SizedBox(width: 8),
                                        Text(
                                          "Your ideas unlocked.",
                                          style: TextStyle(
                                            fontSize: 11,
                                            fontWeight: FontWeight.w500,
                                          ),
                                        ),
                                      ],
                                    ),
                                    SizedBox(height: 22),
                                    Container(
                                      height: 5,
                                      width: 145,
                                      decoration: BoxDecoration(
                                        color: Color(0xFFE8E6FF),
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                    ),
                                    SizedBox(height: 7),
                                    Container(
                                      height: 5,
                                      width: 105,
                                      decoration: BoxDecoration(
                                        color: Color(0xFFE8E6FF),
                                      ),
                                    ),
                                    Spacer(),
                                    Center(
                                      child: Icon(
                                        Icons.show_chart_rounded,
                                        color: Color(0xFF5965F0),
                                        size: 70,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                          Positioned(
                            right: 0,
                            top: 20,
                            child: Container(
                              padding: EdgeInsets.all(13),
                              decoration: BoxDecoration(
                                color: AppColors.primaryColor,
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Icon(
                                Icons.auto_awesome,
                                color: Colors.white,
                                size: 25,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  SizedBox(height: 35),
                  Text(
                    "YOUR PERSONAL AI TEACHER",
                    style: TextStyle(
                      fontSize: 10,
                      color: Color(0xFF5965F0),
                      fontWeight: FontWeight.w500,
                      letterSpacing: 0.4,
                    ),
                  ),
                  SizedBox(height: 12),
                  Text(
                    "Learn Smarter.\nUnderstand Deeper.",
                    style: TextStyle(
                      fontSize: 27,
                      height: 1.12,
                      fontWeight: FontWeight.w400,
                      color: Color(0xFF25252B),
                    ),
                  ),
                  SizedBox(height: 12),
                  Text(
                    "Turn your PDFs into clear explanations, "
                    "throughtful answer, and practice that sticks",
                    style: TextStyle(
                      fontSize: 13,
                      height: 1.5,
                      color: Color(0xFF818092),
                    ),
                  ),
                  ],
                 ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.pushNamed(context, "/register");
                      },
                      icon: Icon(Icons.arrow_forward, size: 18),
                      label: Text('Start my learning journey'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primaryColor,
                        foregroundColor: Colors.white,
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ),
                  SizedBox(height: 12),
            
                  Center(
                    child: Wrap(
                      alignment: WrapAlignment.center,
                      children: [
                        Text(
                          'Already have an account? ',
                          style: TextStyle(
                            fontSize: 13,
                            color: Color(0xFF626174),
                          ),
                        ),
                        GestureDetector(
                          onTap: () {
                            Navigator.pushNamed(context, "/login");
                          },
                          child: Text(
                            'Sign in',
                            style: TextStyle(
                              fontSize: 13,
                              color: Color(0xFF3849E8),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
            
                  SizedBox(height: 16),
                  Center(
                    child: Text(
                      'Your notes. Your pace. Your potential.',
                      style: TextStyle(fontSize: 11, color: Color(0xFF8B8999)),
                    ),
                  ),
                    ],
                  )
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
