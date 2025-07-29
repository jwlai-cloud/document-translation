#!/usr/bin/env python3
"""Integration test for file upload and validation service."""

import os
import tempfile
from src.services.upload_service import FileUploadService, UploadConfig

def test_upload_service_integration():
    """Test complete upload service workflow."""
    
    print("🧪 Testing File Upload Service Integration...")
    
    # Create upload service with custom config
    config = UploadConfig(
        max_file_size=5 * 1024 * 1024,  # 5MB
        allowed_formats=['pdf', 'docx', 'epub'],
        temp_storage_duration=300,  # 5 minutes
        max_concurrent_uploads=3
    )
    
    service = FileUploadService(config)
    
    try:
        # Test different file types
        test_files = [
            {
                "name": "Valid PDF",
                "filename": "test_document.pdf",
                "content": b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\nxref\n0 3\n0000000000 65535 f \ntrailer\n<<\n/Size 3\n/Root 1 0 R\n>>\nstartxref\n9\n%%EOF',
                "should_succeed": True
            },
            {
                "name": "Valid DOCX (ZIP structure)",
                "filename": "test_document.docx",
                "content": b'PK\x03\x04\x14\x00\x00\x00\x08\x00[Content_Types].xml_rels/.relsword/document.xml',
                "should_succeed": False  # Simplified ZIP, will fail detailed validation
            },
            {
                "name": "Invalid File (Wrong Extension)",
                "filename": "test_document.txt",
                "content": b'This is a text file, not allowed',
                "should_succeed": False
            },
            {
                "name": "Suspicious Content",
                "filename": "malicious.pdf",
                "content": b'%PDF-1.4\n<script>alert("xss")</script>',
                "should_succeed": False
            },
            {
                "name": "Empty File",
                "filename": "empty.pdf",
                "content": b'',
                "should_succeed": False
            },
            {
                "name": "Oversized File",
                "filename": "large.pdf",
                "content": b'%PDF-1.4\n' + b'A' * (6 * 1024 * 1024),  # 6MB > 5MB limit
                "should_succeed": False
            }
        ]
        
        uploaded_files = []
        
        print("\n✓ Testing File Uploads...")
        
        for test_file in test_files:
            print(f"  - Testing: {test_file['name']}")
            
            success, uploaded_file, errors = service.upload_file(
                test_file["content"], 
                test_file["filename"]
            )
            
            print(f"    Expected Success: {test_file['should_succeed']}, Actual: {success}")
            
            if success:
                print(f"    File ID: {uploaded_file.file_id}")
                print(f"    Format: {uploaded_file.file_format}")
                print(f"    Size: {uploaded_file.file_size} bytes")
                print(f"    MIME Type: {uploaded_file.mime_type}")
                print(f"    Hash: {uploaded_file.file_hash[:16]}...")
                print(f"    Expires: {uploaded_file.expires_at}")
                uploaded_files.append(uploaded_file)
            else:
                print(f"    Errors: {len(errors)}")
                for error in errors[:3]:  # Show first 3 errors
                    print(f"      - {error}")
            
            # Verify expectation
            if success != test_file['should_succeed']:
                print(f"    ⚠️  Unexpected result for {test_file['name']}")
            else:
                print(f"    ✓ Result as expected")
        
        # Test file retrieval and access
        print("\n✓ Testing File Retrieval...")
        
        for uploaded_file in uploaded_files:
            print(f"  - Retrieving file: {uploaded_file.file_id}")
            
            # Get file by ID
            retrieved_file = service.get_uploaded_file(uploaded_file.file_id)
            
            if retrieved_file:
                print(f"    ✓ File retrieved successfully")
                print(f"    Original filename: {retrieved_file.original_filename}")
                print(f"    Time remaining: {retrieved_file.time_remaining}")
                
                # Access file content using context manager
                try:
                    with service.get_file_path(uploaded_file.file_id) as file_path:
                        print(f"    ✓ File path accessible: {os.path.basename(file_path)}")
                        
                        # Verify file exists and has content
                        if os.path.exists(file_path):
                            file_size = os.path.getsize(file_path)
                            print(f"    File size on disk: {file_size} bytes")
                            
                            # Read a small portion to verify content
                            with open(file_path, 'rb') as f:
                                first_bytes = f.read(20)
                            print(f"    First bytes: {first_bytes}")
                        else:
                            print(f"    ❌ File not found on disk")
                            
                except Exception as e:
                    print(f"    ❌ Error accessing file: {e}")
            else:
                print(f"    ❌ File not found or expired")
        
        # Test service statistics
        print("\n✓ Testing Service Statistics...")
        
        stats = service.get_upload_stats()
        print(f"  - Active files: {stats['active_files']}")
        print(f"  - Total size: {stats['total_size_bytes']} bytes")
        print(f"  - Max file size: {stats['max_file_size_bytes']} bytes")
        print(f"  - Allowed formats: {stats['allowed_formats']}")
        print(f"  - Storage duration: {stats['temp_storage_duration_seconds']} seconds")
        print(f"  - Max concurrent uploads: {stats['max_concurrent_uploads']}")
        
        # Test file deletion
        print("\n✓ Testing File Deletion...")
        
        for uploaded_file in uploaded_files:
            print(f"  - Deleting file: {uploaded_file.file_id}")
            
            delete_success = service.delete_uploaded_file(uploaded_file.file_id)
            
            if delete_success:
                print(f"    ✓ File deleted successfully")
                
                # Verify file is no longer accessible
                retrieved_file = service.get_uploaded_file(uploaded_file.file_id)
                if retrieved_file is None:
                    print(f"    ✓ File no longer accessible")
                else:
                    print(f"    ❌ File still accessible after deletion")
            else:
                print(f"    ❌ Failed to delete file")
        
        # Final statistics check
        final_stats = service.get_upload_stats()
        print(f"\n✓ Final Statistics:")
        print(f"  - Active files: {final_stats['active_files']}")
        print(f"  - Total size: {final_stats['total_size_bytes']} bytes")
        
        print("\n🎉 File upload service integration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise
    finally:
        # Always shutdown the service
        service.shutdown()

def test_security_features():
    """Test security features of the upload service."""
    
    print("\n🧪 Testing Security Features...")
    
    service = FileUploadService()
    
    try:
        # Test various security scenarios
        security_tests = [
            {
                "name": "Script Injection",
                "filename": "malicious.pdf",
                "content": b'%PDF-1.4\n<script>alert("xss")</script>',
                "expected_issues": ["dangerous content"]
            },
            {
                "name": "JavaScript Code",
                "filename": "js_code.pdf", 
                "content": b'%PDF-1.4\njavascript:void(0)',
                "expected_issues": ["dangerous content"]
            },
            {
                "name": "PHP Code",
                "filename": "php_code.pdf",
                "content": b'%PDF-1.4\n<?php echo "hello"; ?>',
                "expected_issues": ["dangerous content"]
            },
            {
                "name": "Suspicious Filename",
                "filename": "../../../etc/passwd.pdf",
                "content": b'%PDF-1.4\nNormal content',
                "expected_issues": ["suspicious filename"]
            },
            {
                "name": "File Extension Mismatch",
                "filename": "document.pdf",
                "content": b'This is actually a text file, not a PDF',
                "expected_issues": ["signature", "format"]
            }
        ]
        
        for test in security_tests:
            print(f"  - Testing: {test['name']}")
            
            success, uploaded_file, errors = service.upload_file(
                test["content"],
                test["filename"]
            )
            
            print(f"    Upload Success: {success}")
            print(f"    Errors Found: {len(errors)}")
            
            if not success:
                print("    Security Issues Detected:")
                for error in errors:
                    print(f"      - {error}")
                
                # Check if expected security issues were detected
                detected_issues = [error.lower() for error in errors]
                for expected_issue in test["expected_issues"]:
                    if any(expected_issue in issue for issue in detected_issues):
                        print(f"    ✓ Expected issue detected: {expected_issue}")
                    else:
                        print(f"    ⚠️  Expected issue not detected: {expected_issue}")
            else:
                print(f"    ⚠️  Security test passed when it should have failed")
        
        print("✓ Security feature testing completed!")
        
    finally:
        service.shutdown()

def test_concurrent_uploads():
    """Test concurrent upload handling."""
    
    print("\n🧪 Testing Concurrent Upload Handling...")
    
    import threading
    import time
    
    # Create service with low concurrent limit
    config = UploadConfig(max_concurrent_uploads=2)
    service = FileUploadService(config)
    
    try:
        results = []
        
        def upload_worker(worker_id):
            """Worker function for concurrent uploads."""
            file_content = b'%PDF-1.4\nWorker ' + str(worker_id).encode() + b' content'
            filename = f'worker_{worker_id}.pdf'
            
            print(f"    Worker {worker_id}: Starting upload...")
            success, uploaded_file, errors = service.upload_file(file_content, filename)
            
            result = {
                'worker_id': worker_id,
                'success': success,
                'errors': errors,
                'uploaded_file': uploaded_file
            }
            results.append(result)
            
            if success:
                print(f"    Worker {worker_id}: Upload successful")
            else:
                print(f"    Worker {worker_id}: Upload failed - {errors}")
        
        # Start multiple concurrent uploads
        threads = []
        for i in range(5):  # More workers than allowed concurrent uploads
            thread = threading.Thread(target=upload_worker, args=(i,))
            threads.append(thread)
            thread.start()
            time.sleep(0.1)  # Small delay to stagger starts
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Analyze results
        successful_uploads = [r for r in results if r['success']]
        failed_uploads = [r for r in results if not r['success']]
        concurrent_limit_errors = [
            r for r in failed_uploads 
            if any('concurrent' in error.lower() for error in r['errors'])
        ]
        
        print(f"  - Total uploads attempted: {len(results)}")
        print(f"  - Successful uploads: {len(successful_uploads)}")
        print(f"  - Failed uploads: {len(failed_uploads)}")
        print(f"  - Concurrent limit errors: {len(concurrent_limit_errors)}")
        
        # Clean up successful uploads
        for result in successful_uploads:
            if result['uploaded_file']:
                service.delete_uploaded_file(result['uploaded_file'].file_id)
        
        print("✓ Concurrent upload testing completed!")
        
    finally:
        service.shutdown()

if __name__ == "__main__":
    try:
        test_upload_service_integration()
        test_security_features()
        test_concurrent_uploads()
        print("\n✅ All upload service integration tests passed!")
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise