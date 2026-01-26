//
//  APIService.swift
//  WeGo MessagesExtension
//
//  Handles all communication with backend (create chat, send message)
//

import Foundation

// MARK: - Models matching backend
struct NewChatRequest: Codable {
    let chat_name: String
    let user_ids: [String]
}

struct NewChatResponse: Codable {
    let chat_id: String
    let chat_name: String
    let members: [String]
    let created_at: String
}

struct ChatMessageRequest: Codable {
    let user_id: String
    let user_name: String
    let text: String
}

struct ChatMessageResponse: Codable {
    let status: String?
    let message_id: String?
    let error: String?
}

struct FetchMessagesResponse: Codable {
    let messages: [BackendMessage]
}

struct BackendMessage: Codable {
    let message_id: String
    let user_id: String
    let user_name: String
    let text: String
    let timestamp: String
    
    // Convert to ChatMessage
    func toChatMessage() -> ChatMessage {
        // Parse ISO8601 timestamp or use current date if parsing fails
        let dateFormatter = ISO8601DateFormatter()
        let date = dateFormatter.date(from: timestamp) ?? Date()
        
        return ChatMessage(
            id: message_id,
            text: text,
            sender: user_id,
            senderName: user_name,
            timestamp: date
        )
    }
}

// MARK: - API Service
final class APIService {
    static let shared = APIService()
    private init() {}
    
    // ✅ Update this base URL if ngrok refreshes
    private let baseURL = "https://cynthia-weatherworn-unprotestingly.ngrok-free.dev/api/v1"
    
    // MARK: - Create New Chat
    func createNewChat(chatName: String, userIds: [String], completion: @escaping (Result<NewChatResponse, Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/chats") else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        let body = NewChatRequest(chat_name: chatName, user_ids: userIds)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            request.httpBody = try JSONEncoder().encode(body)
        } catch {
            completion(.failure(error))
            return
        }
        
        perform(request, completion: completion)
    }
    
    // MARK: - Send Chat Message
    func sendMessage(chatId: String, userId: String, userName: String, text: String, completion: @escaping (Result<ChatMessageResponse, Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/chats/\(chatId)/messages") else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        let body = ChatMessageRequest(user_id: userId, user_name: userName, text: text)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            request.httpBody = try JSONEncoder().encode(body)
        } catch {
            completion(.failure(error))
            return
        }
        
        perform(request, completion: completion)
    }
    
    // MARK: - Fetch Messages
    func fetchMessages(chatId: String, completion: @escaping (Result<[ChatMessage], Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/chats/\(chatId)/messages") else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        perform(request) { (result: Result<FetchMessagesResponse, Error>) in
            switch result {
            case .success(let response):
                let chatMessages = response.messages.map { $0.toChatMessage() }
                completion(.success(chatMessages))
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
    
    // MARK: - Internal Generic Request Performer
    private func perform<T: Decodable>(_ request: URLRequest, completion: @escaping (Result<T, Error>) -> Void) {
        URLSession.shared.dataTask(with: request) { data, response, error in
            // Networking error
            if let error = error {
                completion(.failure(error))
                return
            }
            
            // Invalid status code
            if let httpResponse = response as? HTTPURLResponse, !(200...299).contains(httpResponse.statusCode) {
                let message = "HTTP Error: \(httpResponse.statusCode)"
                completion(.failure(APIError.serverError(message)))
                return
            }
            
            // Decode response
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            
            do {
                let decoded = try JSONDecoder().decode(T.self, from: data)
                completion(.success(decoded))
            } catch {
                print("⚠️ JSON Decoding Error: \(error)")
                print("Response: \(String(data: data, encoding: .utf8) ?? "nil")")
                completion(.failure(error))
            }
        }.resume()
    }
}

// MARK: - API Error Enum
enum APIError: Error, LocalizedError {
    case invalidURL
    case serverError(String)
    case noData
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL."
        case .serverError(let msg): return "Server error: \(msg)"
        case .noData: return "No data returned."
        }
    }
}
