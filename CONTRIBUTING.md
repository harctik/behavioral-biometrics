# Contributing to Behavior-Based Authentication System

Thank you for considering contributing to this project! This document provides guidelines and instructions for contributing.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Git Workflow](#git-workflow)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Collaborate openly

## Getting Started

1. **Fork the repository**
2. **Clone your fork**
   ```bash
   git clone https://github.com/your-username/behavior-auth.git
   cd behavior-auth
   ```
3. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

### Prerequisites

- Python 3.10, 3.11, or 3.12
- pip (Python package manager)
- Git

### Installation

1. **Create virtual environment**
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   
   # Windows (Command Prompt)
   python -m venv venv
   venv\Scripts\activate.bat
   
   # macOS/Linux
   python -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Set up environment variables**
   ```bash
   # Copy example env file
   copy .env.example .env  # Windows
   cp .env.example .env    # macOS/Linux
   
   # Edit .env and set required variables:
   # - SECRET_KEY (required)
   # - JWT_SECRET_KEY (required)
   ```

4. **Run the application**
   ```bash
   # Development mode
   flask run
   
   # Or using the entry point
   behavior-auth
   ```

## Code Style

### Python

We use **Black** for code formatting and **Ruff** for linting.

```bash
# Format code
black app/ tests/

# Check formatting
black --check app/ tests/

# Lint code
ruff check app/ tests/

# Run type checking (optional)
mypy app/
```

**Configuration:**
- Line length: 88 characters (Black default)
- Target Python: 3.10+
- Follow PEP 8 style guide

**Docstrings:**
- Use Google-style docstrings
- Document all public functions, classes, and methods
- Include Args, Returns, and Raises sections

Example:
```python
def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate a user with username and password.
    
    Args:
        username: User's username
        password: User's password
        
    Returns:
        User dictionary if authentication successful, None otherwise
        
    Raises:
        ValueError: If username or password is invalid
    """
    pass
```

### JavaScript

- Use camelCase for variables and functions
- Use PascalCase for classes and components
- Use const/let instead of var
- Add semicolons
- Use single quotes for strings

Example:
```javascript
const MAX_ATTEMPTS = 5;

function validateInput(input) {
    if (!input) {
        throw new Error('Input is required');
    }
    return input.trim();
}
```

## Git Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `test/description` - Test additions/changes

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Maintenance

**Examples:**
```
feat(auth): add rate limiting to login endpoint

fix(db): resolve connection leak in session management

docs(readme): update installation instructions for Windows
```

### Making Changes

1. **Stage changes**
   ```bash
   git add <file>
   ```

2. **Commit**
   ```bash
   git commit -m "feat(feature-name): add new functionality"
   ```

3. **Push**
   ```bash
   git push origin feature/your-feature-name
   ```

## Pull Request Process

1. **Update documentation** if adding/changing features
2. **Add tests** for new functionality
3. **Ensure tests pass**
   ```bash
   pytest
   ```
4. **Run linters**
   ```bash
   black --check app/ tests/
   ruff check app/ tests/
   ```
5. **Update CHANGELOG.md** (if applicable)
6. **Create Pull Request**
   - Use the PR template
   - Link related issues
   - Request review from maintainers

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
coverage run -m pytest
coverage report

# Run specific test file
pytest tests/test_comprehensive.py -v

# Run tests matching pattern
pytest -k "test_login" -v
```

### Writing Tests

- Use pytest framework
- Name test functions with `test_` prefix
- Use descriptive test names
- Test one thing per test function
- Use fixtures for setup/teardown

Example:
```python
def test_user_authentication_success():
    """Test successful user authentication."""
    db = create_db_manager(":memory:")
    db.create_user("testuser", "test@example.com", "password123")
    
    user = db.authenticate_user("testuser", "password123")
    
    assert user is not None
    assert user["username"] == "testuser"
```

### Coverage Requirements

- Minimum 70% code coverage
- Focus on critical paths:
  - Authentication flow
  - Database operations
  - ML model predictions
  - Security features

## Documentation

### README Updates

Update README.md when:
- Adding new features
- Changing installation steps
- Modifying configuration
- Updating API endpoints

### API Documentation

We use OpenAPI/Swagger for API docs. Update API documentation when:
- Adding new endpoints
- Changing request/response formats
- Modifying authentication requirements

### Code Comments

- Explain **why**, not just **what**
- Document complex algorithms
- Note any limitations or TODOs
- Include references to related issues/PRs

## Security

When contributing security-related code:
- Never commit secrets or credentials
- Use environment variables for sensitive data
- Follow security best practices
- Report vulnerabilities privately to maintainers

## Questions?

- Open an issue for questions
- Check existing issues and PRs
- Join discussions in relevant issues

## Thank You!

Your contributions make this project better for everyone. We appreciate your time and effort! 🎉
