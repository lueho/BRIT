# BRIT Core Module

## Overview
The BRIT Core Module is the central component of the Bioresource Inventory Tool (BRIT). It serves as the main Django project module that integrates all other modules and provides the core functionality and configuration for the entire application.

## Features
- Main project configuration and settings
- URL routing for all modules
- Core views for main pages (Home, About, Learning, Privacy Policy)
- Integration of all other modules
- Authentication and authorization management
- Caching configuration
- Static and media file handling
- REST API configuration

## Components

### Settings
The settings package contains the main configuration for the entire application, including:
- Database configuration
- Installed apps
- Middleware
- Authentication settings
- Caching (Redis)
- AWS S3 storage configuration
- REST framework settings
- Email settings

### URLs
The urls.py file defines the URL routing for the entire application, connecting all modules and their respective URL patterns.

### Views
The core views include:
- HomeView - The main landing page
- AboutView - Information about the project
- LearningView - Educational content
- PrivacyPolicyView - Privacy policy information
- CacheTestView - Testing caching functionality
- Session management utilities

### Templates
The module includes templates for the core pages of the application, providing a consistent user interface.

## Integration
The BRIT Core Module integrates all other modules of the application:
- bibliography
- case_studies
- distributions
- interfaces
- inventories
- layer_manager
- maps
- materials
- sources
- users
- utils

## Dependencies
The application relies on several key technologies:
- Django web framework
- PostgreSQL database
- Redis for caching
- AWS S3 for file storage
- Django REST framework for API functionality