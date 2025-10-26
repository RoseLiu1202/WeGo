//
//  MessagesViewController.swift
//  PlanningAgent iMessage Extension
//
//  Fixed to use APIService for proper database integration
//

import UIKit
import Messages

// MARK: - Chat Models
struct ChatMessage: Codable {
    let id: String
    let text: String
    let sender: String
    let senderName: String
    let timestamp: Date
    
    init(text: String, sender: String, senderName: String) {
        self.id = UUID().uuidString
        self.text = text
        self.sender = sender
        self.senderName = senderName
        self.timestamp = Date()
    }
    
    // Initialize from backend message
    init(id: String, text: String, sender: String, senderName: String, timestamp: Date) {
        self.id = id
        self.text = text
        self.sender = sender
        self.senderName = senderName
        self.timestamp = timestamp
    }
}

struct ChatSession: Codable {
    var messages: [ChatMessage] = []
    var participants: [String: String] = [:]
}

// MARK: - MessagesViewController
class MessagesViewController: MSMessagesAppViewController {
    
    // MARK: - Properties
    private var chatSession = ChatSession()
    private var currentUserID = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
    private var currentUserName = "You"
    private var isInitialPromptShown = false
    private let chatId = "d3TS2ZNJ5LmUEtzXRvNt" // Your hardcoded chat ID
    
    // Polling timer to fetch new messages
    private var pollingTimer: Timer?
    private let pollingInterval: TimeInterval = 2.0 // Poll every 2 seconds for real-time feel
    private var lastMessageCount = 0 // Track message count to detect changes
    
    private var inputBottomConstraint: NSLayoutConstraint!
    
    // MARK: - UI Elements
    private let headerLabel: UILabel = {
        let label = UILabel()
        label.text = "🤝 Group Planning Chat"
        label.font = .systemFont(ofSize: 18, weight: .bold)
        label.textAlignment = .center
        label.textColor = .label
        label.translatesAutoresizingMaskIntoConstraints = false
        return label
    }()
    
    private let participantLabel: UILabel = {
        let label = UILabel()
        label.text = "1 participant"
        label.font = .systemFont(ofSize: 12)
        label.textColor = .secondaryLabel
        label.textAlignment = .center
        label.translatesAutoresizingMaskIntoConstraints = false
        return label
    }()
    
    private let tableView: UITableView = {
        let t = UITableView()
        t.translatesAutoresizingMaskIntoConstraints = false
        t.backgroundColor = .systemGroupedBackground
        t.separatorStyle = .none
        t.keyboardDismissMode = .interactive
        t.contentInsetAdjustmentBehavior = .never
        return t
    }()
    
    private let inputContainerView: UIView = {
        let v = UIView()
        v.backgroundColor = .systemBackground
        v.translatesAutoresizingMaskIntoConstraints = false
        return v
    }()
    
    private let messageTextField: UITextField = {
        let tf = UITextField()
        tf.placeholder = "Type a message..."
        tf.backgroundColor = .systemGray6
        tf.layer.cornerRadius = 20
        tf.leftView = UIView(frame: CGRect(x: 0, y: 0, width: 15, height: 0))
        tf.leftViewMode = .always
        tf.returnKeyType = .send
        tf.translatesAutoresizingMaskIntoConstraints = false
        return tf
    }()
    
    private let sendButton: UIButton = {
        let b = UIButton(type: .system)
        b.setImage(UIImage(systemName: "arrow.up.circle.fill"), for: .normal)
        b.tintColor = .systemBlue
        b.contentVerticalAlignment = .fill
        b.contentHorizontalAlignment = .fill
        b.translatesAutoresizingMaskIntoConstraints = false
        return b
    }()
    
    // MARK: - Lifecycle
    override func viewDidLoad() {
        super.viewDidLoad()
        setupUI()
        setupTableView()
        setupKeyboardObservers()
        setupActions()
        loadOrCreateSession()
    }
    
    // MARK: - UI Setup
    private func setupUI() {
        view.backgroundColor = .systemGroupedBackground
        
        view.addSubview(headerLabel)
        view.addSubview(participantLabel)
        view.addSubview(tableView)
        view.addSubview(inputContainerView)
        inputContainerView.addSubview(messageTextField)
        inputContainerView.addSubview(sendButton)
        
        // Layout constraints - Using keyboardLayoutGuide for proper keyboard handling
        inputBottomConstraint = inputContainerView.bottomAnchor.constraint(equalTo: view.keyboardLayoutGuide.topAnchor)
        
        NSLayoutConstraint.activate([
            // Header
            headerLabel.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 8),
            headerLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            headerLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            
            participantLabel.topAnchor.constraint(equalTo: headerLabel.bottomAnchor, constant: 2),
            participantLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            participantLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            
            // Table view (between header and input)
            tableView.topAnchor.constraint(equalTo: participantLabel.bottomAnchor, constant: 8),
            tableView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            tableView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            tableView.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor),

            // Input bar
            inputContainerView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            inputContainerView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            inputBottomConstraint,
            inputContainerView.heightAnchor.constraint(equalToConstant: 60),
            
            // Text field & send button
            messageTextField.leadingAnchor.constraint(equalTo: inputContainerView.leadingAnchor, constant: 15),
            messageTextField.trailingAnchor.constraint(equalTo: sendButton.leadingAnchor, constant: -10),
            messageTextField.centerYAnchor.constraint(equalTo: inputContainerView.centerYAnchor),
            messageTextField.heightAnchor.constraint(equalToConstant: 40),
            
            sendButton.trailingAnchor.constraint(equalTo: inputContainerView.trailingAnchor, constant: -15),
            sendButton.centerYAnchor.constraint(equalTo: inputContainerView.centerYAnchor),
            sendButton.widthAnchor.constraint(equalToConstant: 36),
            sendButton.heightAnchor.constraint(equalToConstant: 36)
        ])
        
        // Optional subtle shadow like Messages
        inputContainerView.layer.shadowColor = UIColor.black.cgColor
        inputContainerView.layer.shadowOpacity = 0.1
        inputContainerView.layer.shadowRadius = 6
        inputContainerView.layer.shadowOffset = CGSize(width: 0, height: -2)
    }
    
    private func setupTableView() {
        tableView.dataSource = self
        tableView.delegate = self
        tableView.register(ChatMessageCell.self, forCellReuseIdentifier: "ChatMessageCell")
    }
    
    private func setupActions() {
        sendButton.addTarget(self, action: #selector(sendButtonTapped), for: .touchUpInside)
        messageTextField.delegate = self
    }
    
    // MARK: - Keyboard Handling
    private func setupKeyboardObservers() {
        // Add tap gesture to dismiss keyboard
        let tapGesture = UITapGestureRecognizer(target: self, action: #selector(dismissKeyboard))
        tapGesture.cancelsTouchesInView = false
        tableView.addGestureRecognizer(tapGesture)
        
        // Observe keyboard notifications for scrolling table view
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(keyboardWillShow),
            name: UIResponder.keyboardWillShowNotification,
            object: nil
        )
        
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(keyboardWillHide),
            name: UIResponder.keyboardWillHideNotification,
            object: nil
        )
    }
    
    @objc private func dismissKeyboard() {
        view.endEditing(true)
    }
    
    @objc private func keyboardWillShow(_ notification: Notification) {
        guard let keyboardFrame = notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect,
              let duration = notification.userInfo?[UIResponder.keyboardAnimationDurationUserInfoKey] as? Double else {
            return
        }
        
        // Adjust table view content inset to account for keyboard
        let keyboardHeight = keyboardFrame.height
        
        UIView.animate(withDuration: duration) {
            self.tableView.contentInset.bottom = keyboardHeight
            self.tableView.verticalScrollIndicatorInsets.bottom = keyboardHeight
            self.scrollToBottom(animated: false)
        }
    }
    
    @objc private func keyboardWillHide(_ notification: Notification) {
        guard let duration = notification.userInfo?[UIResponder.keyboardAnimationDurationUserInfoKey] as? Double else {
            return
        }
        
        UIView.animate(withDuration: duration) {
            self.tableView.contentInset.bottom = 0
            self.tableView.verticalScrollIndicatorInsets.bottom = 0
        }
    }
    
    // MARK: - Actions
    @objc private func sendButtonTapped() {
        sendMessage()
    }
    
    private func sendMessage() {
        guard let text = messageTextField.text?.trimmingCharacters(in: .whitespacesAndNewlines),
              !text.isEmpty else {
            return
        }
        
        // Clear the text field immediately for better UX
        messageTextField.text = ""
        
        // Send to backend using APIService - THIS IS THE KEY FIX!
        print("📤 Sending message to backend...")
        APIService.shared.sendMessage(
            chatId: chatId,
            userId: currentUserID,
            userName: currentUserName,
            text: text
        ) { [weak self] result in
            switch result {
            case .success(let response):
                print("✅ Message sent successfully: \(response.message_id ?? "unknown ID")")
                // Immediately fetch messages to update UI with the new message from backend
                self?.fetchMessagesFromBackend()
                
            case .failure(let error):
                print("❌ Failed to send message: \(error.localizedDescription)")
                // Show error to user
                DispatchQueue.main.async {
                    self?.showErrorAlert(message: "Failed to send message: \(error.localizedDescription)")
                }
            }
        }
    }
    
    private func scrollToBottom(animated: Bool) {
        guard chatSession.messages.count > 0 else { return }
        
        DispatchQueue.main.async {
            let indexPath = IndexPath(row: self.chatSession.messages.count - 1, section: 0)
            self.tableView.scrollToRow(at: indexPath, at: .bottom, animated: animated)
        }
    }
    
    // MARK: - API Integration - NOW USING APIService!
    private func fetchMessagesFromBackend() {
        print("📥 Fetching messages from backend...")
        
        APIService.shared.fetchMessages(chatId: chatId) { [weak self] result in
            guard let self = self else { return }
            
            switch result {
            case .success(let messages):
                print("✅ Fetched \(messages.count) messages from backend")
                
                // Update UI on main thread
                DispatchQueue.main.async {
                    let previousCount = self.chatSession.messages.count
                    self.chatSession.messages = messages
                    self.lastMessageCount = messages.count
                    
                    // Reload table view
                    self.tableView.reloadData()
                    
                    // Scroll to bottom if new messages arrived
                    if messages.count > previousCount {
                        self.scrollToBottom(animated: true)
                    }
                }
                
            case .failure(let error):
                print("❌ Failed to fetch messages: \(error.localizedDescription)")
            }
        }
    }
    
    private func startPolling() {
        // Stop any existing timer
        pollingTimer?.invalidate()
        
        // Start a new timer
        pollingTimer = Timer.scheduledTimer(withTimeInterval: pollingInterval, repeats: true) { [weak self] _ in
            self?.fetchMessagesFromBackend()
        }
        
        // Fetch immediately when polling starts
        fetchMessagesFromBackend()
        
        print("🔄 Started polling for messages every \(pollingInterval) seconds")
    }
    
    private func stopPolling() {
        pollingTimer?.invalidate()
        pollingTimer = nil
        print("⏸️ Stopped polling for messages")
    }
    
    // MARK: - Session Management
    private func loadOrCreateSession() {
        // Start polling when the view loads
        startPolling()
        
        // Add current user to participants if not already there
        if chatSession.participants[currentUserID] == nil {
            chatSession.participants[currentUserID] = currentUserName
        }
        
        updateParticipantLabel()
    }
    
    private func updateParticipantLabel() {
        let count = chatSession.participants.count
        participantLabel.text = "\(count) participant\(count == 1 ? "" : "s")"
    }
    
    // MARK: - Error Handling
    private func showErrorAlert(message: String) {
        let alert = UIAlertController(
            title: "Error",
            message: message,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
    
    // MARK: - MSMessagesAppViewController
    override func willBecomeActive(with conversation: MSConversation) {
        super.willBecomeActive(with: conversation)
        
        // Start polling when becoming active
        startPolling()
        
        // Load session from the conversation's selected message (if any)
        if let message = conversation.selectedMessage,
           let url = message.url {
            parseSessionFromURL(url)
        }
    }
    
    override func didResignActive(with conversation: MSConversation) {
        super.didResignActive(with: conversation)
        
        // Stop polling when inactive to save resources
        stopPolling()
    }
    
    private func parseSessionFromURL(_ url: URL) {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            print("❌ Could not parse URL components")
            return
        }
        
        // Extract session data from URL
        if let sessionQuery = components.queryItems?.first(where: { $0.name == "session" })?.value,
           let sessionData = sessionQuery.data(using: .utf8),
           let decodedSession = try? JSONDecoder().decode(ChatSession.self, from: sessionData) {
            
            chatSession = decodedSession
            print("✅ Loaded shared session with \(chatSession.messages.count) messages")
            
            // Update UI
            updateParticipantLabel()
            tableView.reloadData()
            scrollToBottom(animated: false)
        } else {
            print("📭 Could not decode session, starting fresh")
            loadOrCreateSession()
        }
    }
    
    deinit {
        pollingTimer?.invalidate()
        NotificationCenter.default.removeObserver(self)
    }
}

// MARK: - UITableView
extension MessagesViewController: UITableViewDataSource, UITableViewDelegate {
    func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        chatSession.messages.count
    }
    
    func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let message = chatSession.messages[indexPath.row]
        let cell = tableView.dequeueReusableCell(withIdentifier: "ChatMessageCell", for: indexPath) as! ChatMessageCell
        
        let isCurrentUser = message.sender == currentUserID
        cell.configure(with: message, isCurrentUser: isCurrentUser)
        
        return cell
    }
    
    func tableView(_ tableView: UITableView, heightForRowAt indexPath: IndexPath) -> CGFloat {
        UITableView.automaticDimension
    }
    
    func tableView(_ tableView: UITableView, estimatedHeightForRowAt indexPath: IndexPath) -> CGFloat {
        80
    }
}

// MARK: - UITextField
extension MessagesViewController: UITextFieldDelegate {
    func textFieldShouldReturn(_ textField: UITextField) -> Bool {
        sendMessage()
        return true
    }
}

// MARK: - ChatMessageCell
class ChatMessageCell: UITableViewCell {
    private let bubbleView = UIView()
    private let messageLabel = UILabel()
    private let senderNameLabel = UILabel()
    private let timestampLabel = UILabel()
    
    // Container for sender name and timestamp
    private let metadataStackView = UIStackView()
    
    // Store constraints to properly manage them
    private var currentUserConstraints: [NSLayoutConstraint] = []
    private var otherUserConstraints: [NSLayoutConstraint] = []
    
    override init(style: UITableViewCell.CellStyle, reuseIdentifier: String?) {
        super.init(style: style, reuseIdentifier: reuseIdentifier)
        setupUI()
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    
    private func setupUI() {
        backgroundColor = .clear
        selectionStyle = .none
        
        // Configure bubble view
        bubbleView.layer.cornerRadius = 16
        bubbleView.layer.masksToBounds = true
        bubbleView.translatesAutoresizingMaskIntoConstraints = false
        
        // Configure sender name label
        senderNameLabel.font = .systemFont(ofSize: 12, weight: .semibold)
        senderNameLabel.textColor = .secondaryLabel
        senderNameLabel.translatesAutoresizingMaskIntoConstraints = false
        
        // Configure timestamp label
        timestampLabel.font = .systemFont(ofSize: 11)
        timestampLabel.textColor = .tertiaryLabel
        timestampLabel.translatesAutoresizingMaskIntoConstraints = false
        
        // Configure message label
        messageLabel.font = .systemFont(ofSize: 16)
        messageLabel.numberOfLines = 0
        messageLabel.translatesAutoresizingMaskIntoConstraints = false
        
        // Configure metadata stack view
        metadataStackView.axis = .horizontal
        metadataStackView.spacing = 6
        metadataStackView.translatesAutoresizingMaskIntoConstraints = false
        metadataStackView.addArrangedSubview(senderNameLabel)
        metadataStackView.addArrangedSubview(timestampLabel)
        
        // Add subviews
        contentView.addSubview(metadataStackView)
        contentView.addSubview(bubbleView)
        bubbleView.addSubview(messageLabel)
        
        // Message label constraints (inside bubble)
        NSLayoutConstraint.activate([
            messageLabel.topAnchor.constraint(equalTo: bubbleView.topAnchor, constant: 8),
            messageLabel.bottomAnchor.constraint(equalTo: bubbleView.bottomAnchor, constant: -8),
            messageLabel.leadingAnchor.constraint(equalTo: bubbleView.leadingAnchor, constant: 12),
            messageLabel.trailingAnchor.constraint(equalTo: bubbleView.trailingAnchor, constant: -12)
        ])
        
        // Set up current user constraints (right-aligned)
        currentUserConstraints = [
            metadataStackView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -12),
            metadataStackView.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 6),
            
            bubbleView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -12),
            bubbleView.topAnchor.constraint(equalTo: metadataStackView.bottomAnchor, constant: 4),
            bubbleView.bottomAnchor.constraint(equalTo: contentView.bottomAnchor, constant: -6),
            bubbleView.widthAnchor.constraint(lessThanOrEqualToConstant: 260),
            bubbleView.leadingAnchor.constraint(greaterThanOrEqualTo: contentView.leadingAnchor, constant: 80)
        ]
        
        // Set up other user constraints (left-aligned)
        otherUserConstraints = [
            metadataStackView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 12),
            metadataStackView.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 6),
            
            bubbleView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 12),
            bubbleView.topAnchor.constraint(equalTo: metadataStackView.bottomAnchor, constant: 4),
            bubbleView.bottomAnchor.constraint(equalTo: contentView.bottomAnchor, constant: -6),
            bubbleView.widthAnchor.constraint(lessThanOrEqualToConstant: 260),
            bubbleView.trailingAnchor.constraint(lessThanOrEqualTo: contentView.trailingAnchor, constant: -80)
        ]
    }
    
    override func prepareForReuse() {
        super.prepareForReuse()
        // Deactivate all bubble constraints before reuse
        NSLayoutConstraint.deactivate(currentUserConstraints)
        NSLayoutConstraint.deactivate(otherUserConstraints)
    }
    
    func configure(with message: ChatMessage, isCurrentUser: Bool) {
        messageLabel.text = message.text
        
        // Set sender name (hide for current user since it's obvious)
        if isCurrentUser {
            senderNameLabel.text = ""
            senderNameLabel.isHidden = true
        } else {
            senderNameLabel.text = message.senderName
            senderNameLabel.isHidden = false
        }
        
        // Set timestamp
        timestampLabel.text = formatTimestamp(message.timestamp)
        
        // Set bubble colors
        bubbleView.backgroundColor = isCurrentUser ? .systemBlue : .systemGray5
        messageLabel.textColor = isCurrentUser ? .white : .label
        
        // Activate the appropriate constraints
        if isCurrentUser {
            NSLayoutConstraint.deactivate(otherUserConstraints)
            NSLayoutConstraint.activate(currentUserConstraints)
        } else {
            NSLayoutConstraint.deactivate(currentUserConstraints)
            NSLayoutConstraint.activate(otherUserConstraints)
        }
    }
    
    private func formatTimestamp(_ timestamp: Date) -> String {
        let formatter = DateFormatter()
        let calendar = Calendar.current
        
        if calendar.isDateInToday(timestamp) {
            formatter.dateFormat = "h:mm a"
        } else if calendar.isDateInYesterday(timestamp) {
            formatter.dateFormat = "'Yesterday' h:mm a"
        } else {
            formatter.dateFormat = "MMM d, h:mm a"
        }
        
        return formatter.string(from: timestamp)
    }
}
