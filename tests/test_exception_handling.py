# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Tests to verify that exception handling does not suppress system-level signals.

This test suite ensures that:
1. BaseException is not caught inappropriately
2. KeyboardInterrupt is not suppressed by broad exception handlers
3. SystemExit is not suppressed by broad exception handlers
4. GeneratorExit is not suppressed by broad exception handlers
"""

import ast
import os
import sys

import pytest


def test_keyboard_interrupt_not_suppressed():
    """Verify that KeyboardInterrupt is not suppressed by broad exception handlers."""
    
    # Simulate a function that uses broad exception handling
    def function_with_exception_handler():
        try:
            # This should not suppress KeyboardInterrupt
            raise KeyboardInterrupt("User interrupted")
        except KeyboardInterrupt:
            # Proper handling: re-raise KeyboardInterrupt
            raise
        except Exception as e:
            # This should not catch KeyboardInterrupt
            pytest.fail(f"Exception handler caught KeyboardInterrupt: {e}")
    
    # Verify KeyboardInterrupt is propagated
    with pytest.raises(KeyboardInterrupt):
        function_with_exception_handler()


def test_system_exit_not_suppressed():
    """Verify that SystemExit is not suppressed by broad exception handlers."""
    
    def function_with_exception_handler():
        try:
            sys.exit(1)
        except KeyboardInterrupt:
            pytest.fail("KeyboardInterrupt handler caught SystemExit")
        except Exception as e:
            # Exception should not catch SystemExit
            # This is correct - SystemExit inherits from BaseException, not Exception
            pytest.fail(f"Exception handler should not catch SystemExit: {e}")
    
    # Verify SystemExit is propagated
    with pytest.raises(SystemExit):
        function_with_exception_handler()


def test_generator_exit_not_suppressed():
    """Verify that GeneratorExit is not suppressed by broad exception handlers."""
    
    def generator_with_exception_handler():
        try:
            yield 1
            yield 2
        except GeneratorExit:
            # Proper handling: re-raise GeneratorExit
            raise
        except Exception as e:
            # This should not catch GeneratorExit
            pytest.fail(f"Exception handler caught GeneratorExit: {e}")
    
    # Verify GeneratorExit is propagated
    gen = generator_with_exception_handler()
    next(gen)
    # Closing should raise GeneratorExit inside generator
    gen.close()


def test_exception_handler_catches_runtime_errors():
    """Verify that Exception handler properly catches application-level exceptions."""
    
    caught = False
    
    def function_with_exception_handler():
        nonlocal caught
        try:
            raise ValueError("Application error")
        except KeyboardInterrupt:
            pytest.fail("KeyboardInterrupt handler caught ValueError")
        except Exception as e:
            # This should catch ValueError
            assert isinstance(e, ValueError)
            caught = True
    
    function_with_exception_handler()
    assert caught, "Exception handler should catch ValueError"


def test_specific_exception_handlers_preferred():
    """Verify that specific exception types are handled before broad Exception."""
    
    value_error_caught = False
    exception_caught = False
    
    def function_with_layered_handlers():
        nonlocal value_error_caught, exception_caught
        try:
            raise ValueError("Specific error")
        except ValueError as e:
            value_error_caught = True
        except Exception as e:
            exception_caught = True
    
    function_with_layered_handlers()
    assert value_error_caught, "ValueError handler should catch ValueError"
    assert not exception_caught, "Broad Exception handler should not be reached"


def test_no_bare_except_in_code():
    """Verify that no bare 'except:' clauses exist in the codebase."""
    bare_except_found = []
    
    class BareExceptChecker(ast.NodeVisitor):
        def visit_ExceptHandler(self, node):
            if node.type is None:
                bare_except_found.append((self.filename, node.lineno))
            self.generic_visit(node)
    
    # Check all Python files in the repository
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    for root, dirs, files in os.walk(repo_root):
        # Skip hidden directories and common exclusions
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        tree = ast.parse(f.read())
                    checker = BareExceptChecker()
                    checker.filename = filepath
                    checker.visit(tree)
                except (OSError, SyntaxError):
                    # Skip files that can't be read or parsed
                    pass
    
    assert not bare_except_found, f"Found bare except clauses in: {bare_except_found}"


def test_no_base_exception_in_code():
    """Verify that no 'except BaseException' clauses exist in the codebase."""
    base_exception_found = []
    
    class BaseExceptionChecker(ast.NodeVisitor):
        def visit_ExceptHandler(self, node):
            if node.type and isinstance(node.type, ast.Name):
                if node.type.id == 'BaseException':
                    base_exception_found.append((self.filename, node.lineno))
            self.generic_visit(node)
    
    # Check all Python files in the repository
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    for root, dirs, files in os.walk(repo_root):
        # Skip hidden directories and common exclusions
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        tree = ast.parse(f.read())
                    checker = BaseExceptionChecker()
                    checker.filename = filepath
                    checker.visit(tree)
                except (OSError, SyntaxError):
                    # Skip files that can't be read or parsed
                    pass
    
    assert not base_exception_found, f"Found BaseException handlers in: {base_exception_found}"


def test_keyboard_interrupt_before_exception_in_main_entries():
    """Verify that main entry points handle KeyboardInterrupt before broad Exception."""
    violations = []
    
    class ExceptionOrderChecker(ast.NodeVisitor):
        def visit_Try(self, node):
            # Check exception handler order in try-except blocks
            keyboard_index = None
            exception_index = None
            
            for i, handler in enumerate(node.handlers):
                if handler.type and isinstance(handler.type, ast.Name):
                    if handler.type.id == 'KeyboardInterrupt':
                        keyboard_index = i
                    elif handler.type.id == 'Exception':
                        exception_index = i
            
            # If both exist, KeyboardInterrupt should come before Exception
            if keyboard_index is not None and exception_index is not None:
                if exception_index < keyboard_index:
                    violations.append((self.filename, node.lineno))
            
            self.generic_visit(node)
    
    # Check main.py files in services
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_files = [
        'embedding/main.py',
        'chunking/main.py',
        'parsing/main.py',
        'summarization/main.py',
        'orchestrator/main.py',
        'reporting/main.py',
        'ingestion/main.py',
        'error-reporting/main.py',
    ]
    
    for main_file in main_files:
        filepath = os.path.join(repo_root, main_file)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    tree = ast.parse(f.read())
                checker = ExceptionOrderChecker()
                checker.filename = filepath
                checker.visit(tree)
            except (OSError, SyntaxError):
                # Skip files that can't be read or parsed
                pass
    
    assert not violations, f"Found Exception before KeyboardInterrupt in: {violations}"
